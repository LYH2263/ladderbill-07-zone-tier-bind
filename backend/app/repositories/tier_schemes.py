import sqlite3


def _row_to_scheme(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    scheme = dict(row)
    scheme["enabled"] = bool(scheme["enabled"])
    scheme["tiers"] = tiers_for_scheme(conn, scheme["id"])
    return scheme


def list_schemes(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM tier_schemes ORDER BY id").fetchall()
    return [_row_to_scheme(conn, r) for r in rows]


def get(conn: sqlite3.Connection, scheme_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM tier_schemes WHERE id=?", (scheme_id,)).fetchone()
    return _row_to_scheme(conn, row) if row else None


def get_by_code(conn: sqlite3.Connection, code: str) -> dict | None:
    row = conn.execute("SELECT * FROM tier_schemes WHERE code=?", (code,)).fetchone()
    return _row_to_scheme(conn, row) if row else None


def get_raw(conn: sqlite3.Connection, scheme_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM tier_schemes WHERE id=?", (scheme_id,)).fetchone()
    return dict(row) if row else None


def tiers_for_scheme(conn: sqlite3.Connection, scheme_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT up_to, price, sort_order FROM tier_scheme_tiers WHERE scheme_id=? ORDER BY sort_order",
        (scheme_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def as_calc_rows(conn: sqlite3.Connection, scheme_id: int) -> list[dict]:
    return [
        {"up_to": r["up_to"], "price": r["price"]}
        for r in tiers_for_scheme(conn, scheme_id)
    ]


def create(conn: sqlite3.Connection, code: str, name: str, tiers: list[dict], enabled: bool) -> int:
    cur = conn.execute(
        "INSERT INTO tier_schemes(code, name, enabled, created_at, updated_at) "
        "VALUES (?,?,?,datetime('now'),datetime('now'))",
        (code, name, 1 if enabled else 0),
    )
    scheme_id = int(cur.lastrowid)
    _replace_tiers(conn, scheme_id, tiers)
    conn.commit()
    return scheme_id


def update(
    conn: sqlite3.Connection,
    scheme_id: int,
    name: str | None,
    tiers: list[dict] | None,
    enabled: bool | None,
) -> None:
    if name is not None:
        conn.execute("UPDATE tier_schemes SET name=?, updated_at=datetime('now') WHERE id=?", (name, scheme_id))
    if enabled is not None:
        conn.execute(
            "UPDATE tier_schemes SET enabled=?, updated_at=datetime('now') WHERE id=?",
            (1 if enabled else 0, scheme_id),
        )
    if tiers is not None:
        _replace_tiers(conn, scheme_id, tiers)
        conn.execute("UPDATE tier_schemes SET updated_at=datetime('now') WHERE id=?", (scheme_id,))
    conn.commit()


def _replace_tiers(conn: sqlite3.Connection, scheme_id: int, tiers: list[dict]) -> None:
    conn.execute("DELETE FROM tier_scheme_tiers WHERE scheme_id=?", (scheme_id,))
    conn.executemany(
        "INSERT INTO tier_scheme_tiers(scheme_id, up_to, price, sort_order) VALUES (?,?,?,?)",
        [
            (scheme_id, t.get("up_to"), float(t["price"]), i + 1)
            for i, t in enumerate(tiers)
        ],
    )
