import sqlite3


def list_all(conn: sqlite3.Connection, zone_code: str | None = None) -> list[dict]:
    if zone_code:
        q = "SELECT * FROM accounts WHERE zone_code=? ORDER BY id"
        return [dict(r) for r in conn.execute(q, (zone_code,)).fetchall()]
    return [dict(r) for r in conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()]


def get(conn: sqlite3.Connection, account_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
    return dict(row) if row else None


def set_zone_code(conn: sqlite3.Connection, account_id: int, zone_code: str | None) -> None:
    conn.execute(
        "UPDATE accounts SET zone_code=? WHERE id=?", (zone_code or None, account_id)
    )
    conn.commit()


def list_zone_codes(conn: sqlite3.Connection) -> list[str]:
    q = "SELECT DISTINCT zone_code FROM accounts WHERE zone_code IS NOT NULL AND zone_code != '' ORDER BY zone_code"
    return [r["zone_code"] for r in conn.execute(q).fetchall()]
