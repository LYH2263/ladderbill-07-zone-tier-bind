import json

from app.db import connect
from app.engines.peak_compare import compare_plain_vs_peak
from app.engines.tier_progressive import calc_bill

# 片区档位方案 / 绑定关系在 07-zone-tier-bind 引入；老库通过 PRAGMA 补列。
GLOBAL_TIER_SEED = [(180, 0.52, 1), (260, 0.62, 2), (None, 0.82, 3)]


def init_db():
    conn = connect()
    conn.executescript(
        """
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
    CREATE TABLE IF NOT EXISTS tier_schemes(
        id INTEGER PRIMARY KEY,
        code TEXT UNIQUE,
        name TEXT,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TEXT,
        updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS tier_scheme_tiers(
        id INTEGER PRIMARY KEY,
        scheme_id INTEGER NOT NULL,
        up_to REAL,
        price REAL NOT NULL,
        sort_order INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS zone_bindings(
        id INTEGER PRIMARY KEY,
        zone_code TEXT NOT NULL UNIQUE,
        scheme_id INTEGER NOT NULL,
        note TEXT,
        created_at TEXT,
        updated_at TEXT
    );
    -- 同一片区任一时刻只能绑一套启用方案：zone_code 直唯一，
    -- 触发器保证所绑方案处于启用状态（停用方案不允许新绑/改绑）。
    CREATE TRIGGER IF NOT EXISTS trg_zone_binding_scheme_enabled
        BEFORE INSERT ON zone_bindings
        WHEN NOT EXISTS (SELECT 1 FROM tier_schemes s WHERE s.id = NEW.scheme_id AND s.enabled = 1)
    BEGIN
        SELECT RAISE(ABORT, 'bound tier scheme is disabled');
    END;
    CREATE TRIGGER IF NOT EXISTS trg_zone_binding_scheme_enabled_upd
        BEFORE UPDATE OF scheme_id ON zone_bindings
        WHEN NOT EXISTS (SELECT 1 FROM tier_schemes s WHERE s.id = NEW.scheme_id AND s.enabled = 1)
    BEGIN
        SELECT RAISE(ABORT, 'bound tier scheme is disabled');
    END;
    """
    )
    _migrate_accounts_zone(conn)
    if conn.execute("SELECT COUNT(*) c FROM accounts").fetchone()["c"] == 0:
        conn.execute(
            "INSERT INTO accounts(name, meter_no, note, zone_code) VALUES (?, ?, ?, ?)",
            ("张家", "M-1001", "对照：正常用量", "Z-A"),
        )
        conn.execute(
            "INSERT INTO accounts(name, meter_no, note, zone_code) VALUES (?, ?, ?, ?)",
            ("李家(种子偏高)", "M-1002", "对照：高用量+尖峰", "Z-B"),
        )
        conn.executemany(
            "INSERT INTO tiers(up_to, price, sort_order) VALUES (?,?,?)",
            GLOBAL_TIER_SEED,
        )
        conn.execute("INSERT INTO readings(account_id, kwh, peak) VALUES (1, 120, 0)")
        conn.execute("INSERT INTO readings(account_id, kwh, peak) VALUES (2, 400, 1)")
        conn.execute("INSERT INTO settings(key, value) VALUES ('peak_factor', '1.2')")
        conn.execute("INSERT INTO settings(key, value) VALUES ('currency', 'CNY')")
        _seed_zone_data(conn)
        tiers = [{"up_to": r[0], "price": r[1]} for r in GLOBAL_TIER_SEED]
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


def _migrate_accounts_zone(conn):
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(accounts)").fetchall()]
    if "zone_code" not in cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN zone_code TEXT")
        conn.commit()


def _seed_zone_data(conn):
    """片区 Z-A 绑定一套完整档位方案；Z-B 不绑定以演示全局回退。"""
    cur = conn.execute(
        "INSERT INTO tier_schemes(code, name, enabled, created_at, updated_at) VALUES (?,?,1,datetime('now'),datetime('now'))",
        ("SCH-ZA", "Z-A 片区夏季方案",),
    )
    scheme_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO tier_scheme_tiers(scheme_id, up_to, price, sort_order) VALUES (?,?,?,?)",
        [
            (scheme_id, 200, 0.54, 1),
            (scheme_id, 300, 0.65, 2),
            (scheme_id, None, 0.88, 3),
        ],
    )
    conn.execute(
        "INSERT INTO zone_bindings(zone_code, scheme_id, note, created_at, updated_at) VALUES (?,?,?,datetime('now'),datetime('now'))",
        ("Z-A", scheme_id, "种子绑定"),
    )
