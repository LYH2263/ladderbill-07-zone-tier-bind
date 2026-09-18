import json

from app.db import connect
from app.engines.peak_compare import compare_plain_vs_peak
from app.engines.tier_progressive import calc_bill

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS accounts(
    id INTEGER PRIMARY KEY, name TEXT, meter_no TEXT, note TEXT, zone_code TEXT);
CREATE TABLE IF NOT EXISTS readings(id INTEGER PRIMARY KEY, account_id INTEGER, kwh REAL, peak INTEGER);
CREATE TABLE IF NOT EXISTS tiers(id INTEGER PRIMARY KEY, up_to REAL, price REAL, sort_order INTEGER);
CREATE TABLE IF NOT EXISTS calc_runs(
    id INTEGER PRIMARY KEY,
    kind TEXT,
    account_id INTEGER,
    input_json TEXT,
    result_json TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS tier_plans(
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'enabled',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS tier_plan_tiers(
    id INTEGER PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES tier_plans(id),
    up_to REAL,
    price REAL NOT NULL,
    sort_order INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS zone_bindings(
    id INTEGER PRIMARY KEY,
    zone_code TEXT NOT NULL,
    plan_id INTEGER NOT NULL REFERENCES tier_plans(id),
    status TEXT NOT NULL DEFAULT 'enabled',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
-- 同一片区任一时刻只能有一条启用绑定
CREATE UNIQUE INDEX IF NOT EXISTS idx_zone_bindings_one_enabled
    ON zone_bindings(zone_code) WHERE status = 'enabled';
"""

# 已有库迁移：accounts 可能缺 zone_code 列
def _migrate(conn):
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(accounts)").fetchall()}
    if "zone_code" not in cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN zone_code TEXT")
    # 老种子户补片区代码，便于演示解析链路
    conn.execute("UPDATE accounts SET zone_code='Z01' WHERE meter_no='M-1001' AND zone_code IS NULL")
    conn.execute("UPDATE accounts SET zone_code='Z02' WHERE meter_no='M-1002' AND zone_code IS NULL")


def _seed_plans(conn):
    """示范档位方案与片区绑定（幂等）。"""
    if conn.execute("SELECT COUNT(*) c FROM tier_plans").fetchone()["c"] > 0:
        return
    cur = conn.execute("INSERT INTO tier_plans(name, status) VALUES ('城区居民方案', 'enabled')")
    plan_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO tier_plan_tiers(plan_id, up_to, price, sort_order) VALUES (?,?,?,?)",
        [(plan_id, 200, 0.55, 1), (plan_id, 300, 0.65, 2), (plan_id, None, 0.88, 3)],
    )
    conn.execute(
        "INSERT INTO zone_bindings(zone_code, plan_id, status) VALUES ('Z01', ?, 'enabled')",
        (plan_id,),
    )


def init_db():
    conn = connect()
    conn.executescript(SCHEMA)
    _migrate(conn)
    _seed_plans(conn)
    if conn.execute("SELECT COUNT(*) c FROM accounts").fetchone()["c"] == 0:
        conn.execute(
            "INSERT INTO accounts(name, meter_no, note, zone_code) VALUES ('张家', 'M-1001', '对照：正常用量', 'Z01')"
        )
        conn.execute(
            "INSERT INTO accounts(name, meter_no, note, zone_code) VALUES ('李家(种子偏高)', 'M-1002', '对照：高用量+尖峰', 'Z02')"
        )
        conn.executemany(
            "INSERT INTO tiers(up_to, price, sort_order) VALUES (?,?,?)",
            [(180, 0.52, 1), (260, 0.62, 2), (None, 0.82, 3)],
        )
        conn.execute("INSERT INTO readings(account_id, kwh, peak) VALUES (1, 120, 0)")
        conn.execute("INSERT INTO readings(account_id, kwh, peak) VALUES (2, 400, 1)")
        conn.execute("INSERT INTO settings(key, value) VALUES ('peak_factor', '1.2')")
        conn.execute("INSERT INTO settings(key, value) VALUES ('currency', 'CNY')")
        tiers = [{"up_to": r[0], "price": r[1]} for r in [(180, 0.52), (260, 0.62), (None, 0.82)]]
        bill1 = calc_bill(120, tiers, 1.0)
        conn.execute(
            "INSERT INTO calc_runs(kind, account_id, input_json, result_json, created_at) VALUES (?,?,?,?,datetime('now'))",
            ("bill", 1, json.dumps({"kwh": 120, "peak": False}), json.dumps(bill1, ensure_ascii=False)),
        )
        cmp2 = compare_plain_vs_peak(400, tiers, 1.2)
        conn.execute(
            "INSERT INTO calc_runs(kind, account_id, input_json, result_json, created_at) VALUES (?,?,?,?,datetime('now'))",
            ("compare", 2, json.dumps({"kwh": 400}), json.dumps(cmp2, ensure_ascii=False)),
        )
    conn.commit()
    conn.close()
