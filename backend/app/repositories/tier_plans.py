import sqlite3


def list_all(conn: sqlite3.Connection) -> list[dict]:
    plans = [
        dict(r)
        for r in conn.execute(
            "SELECT id, name, status, created_at FROM tier_plans ORDER BY id"
        ).fetchall()
    ]
    for p in plans:
        p["tiers"] = tiers_of(conn, p["id"])
    return plans


def get(conn: sqlite3.Connection, plan_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, name, status, created_at FROM tier_plans WHERE id=?", (plan_id,)
    ).fetchone()
    if not row:
        return None
    plan = dict(row)
    plan["tiers"] = tiers_of(conn, plan_id)
    return plan


def tiers_of(conn: sqlite3.Connection, plan_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, up_to, price, sort_order FROM tier_plan_tiers WHERE plan_id=? ORDER BY sort_order",
        (plan_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def as_calc_rows(conn: sqlite3.Connection, plan_id: int) -> list[dict]:
    return [{"up_to": t["up_to"], "price": t["price"]} for t in tiers_of(conn, plan_id)]


def create(conn: sqlite3.Connection, name: str, tiers: list[dict]) -> dict:
    cur = conn.execute("INSERT INTO tier_plans(name, status) VALUES (?, 'enabled')", (name,))
    plan_id = int(cur.lastrowid)
    for i, t in enumerate(tiers, start=1):
        conn.execute(
            "INSERT INTO tier_plan_tiers(plan_id, up_to, price, sort_order) VALUES (?,?,?,?)",
            (plan_id, t.get("up_to"), t["price"], i),
        )
    conn.commit()
    return get(conn, plan_id)
