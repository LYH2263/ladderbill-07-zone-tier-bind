import sqlite3


def list_all(conn: sqlite3.Connection, zone_code: str | None = None) -> list[dict]:
    if zone_code is not None:
        if zone_code == "":
            # 空片区：zone_code 为 NULL 或空串
            q = (
                "SELECT * FROM accounts WHERE zone_code IS NULL OR zone_code = '' "
                "ORDER BY id"
            )
            return [dict(r) for r in conn.execute(q).fetchall()]
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM accounts WHERE zone_code = ? ORDER BY id", (zone_code,)
            ).fetchall()
        ]
    return [dict(r) for r in conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()]


def get(conn: sqlite3.Connection, account_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
    return dict(row) if row else None


def update_zone(conn: sqlite3.Connection, account_id: int, zone_code: str | None) -> bool:
    cur = conn.execute("UPDATE accounts SET zone_code=? WHERE id=?", (zone_code, account_id))
    conn.commit()
    return cur.rowcount > 0


def list_zones(conn: sqlite3.Connection) -> list[dict]:
    """片区代码 + 该片区户数（含未绑定片区），供前端筛选下拉。"""
    q = """
    SELECT zone_code, COUNT(*) AS account_count
    FROM accounts
    GROUP BY zone_code
    ORDER BY zone_code
    """
    return [dict(r) for r in conn.execute(q).fetchall()]
