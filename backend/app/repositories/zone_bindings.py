import sqlite3

COLUMNS = """
SELECT b.id, b.zone_code, b.plan_id, b.status, b.created_at, b.updated_at,
       p.name AS plan_name, p.status AS plan_status
FROM zone_bindings b JOIN tier_plans p ON p.id = b.plan_id
"""


def list_all(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(COLUMNS + " ORDER BY b.zone_code, b.id").fetchall()]


def get(conn: sqlite3.Connection, binding_id: int) -> dict | None:
    row = conn.execute(COLUMNS + " WHERE b.id=?", (binding_id,)).fetchone()
    return dict(row) if row else None


def enabled_for_zone(conn: sqlite3.Connection, zone_code: str) -> dict | None:
    row = conn.execute(
        COLUMNS + " WHERE b.zone_code=? AND b.status='enabled'", (zone_code,)
    ).fetchone()
    return dict(row) if row else None


def create(conn: sqlite3.Connection, zone_code: str, plan_id: int) -> int:
    cur = conn.execute(
        "INSERT INTO zone_bindings(zone_code, plan_id, status) VALUES (?, ?, 'enabled')",
        (zone_code, plan_id),
    )
    conn.commit()
    return int(cur.lastrowid)


def update(
    conn: sqlite3.Connection,
    binding_id: int,
    *,
    zone_code: str | None = None,
    plan_id: int | None = None,
    status: str | None = None,
) -> None:
    row = conn.execute("SELECT * FROM zone_bindings WHERE id=?", (binding_id,)).fetchone()
    if not row:
        return
    conn.execute(
        """
        UPDATE zone_bindings
        SET zone_code=?, plan_id=?, status=?, updated_at=datetime('now')
        WHERE id=?
        """,
        (
            zone_code if zone_code is not None else row["zone_code"],
            plan_id if plan_id is not None else row["plan_id"],
            status if status is not None else row["status"],
            binding_id,
        ),
    )
    conn.commit()
