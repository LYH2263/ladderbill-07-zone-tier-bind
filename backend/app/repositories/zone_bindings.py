import sqlite3


class ZoneConflict(Exception):
    """同一片区重复绑定（或数据库唯一约束被触发）。"""

    def __init__(self, zone_code: str, conflict_scheme_id: int | None = None,
                 conflict_scheme_code: str | None = None):
        super().__init__(f"zone {zone_code!r} already bound")
        self.zone_code = zone_code
        self.conflict_scheme_id = conflict_scheme_id
        self.conflict_scheme_code = conflict_scheme_code


class SchemeDisabled(Exception):
    """尝试把片区绑定到已停用方案。"""

    def __init__(self, scheme_id: int):
        super().__init__(f"scheme {scheme_id} is disabled")
        self.scheme_id = scheme_id


def list_bindings(conn: sqlite3.Connection) -> list[dict]:
    q = """
    SELECT b.id, b.zone_code, b.scheme_id, b.note, b.created_at, b.updated_at,
           s.code AS scheme_code, s.name AS scheme_name, s.enabled AS scheme_enabled
    FROM zone_bindings b
    JOIN tier_schemes s ON s.id = b.scheme_id
    ORDER BY b.zone_code
    """
    rows = conn.execute(q).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["scheme_enabled"] = bool(d["scheme_enabled"])
        out.append(d)
    return out


def get_by_zone(conn: sqlite3.Connection, zone_code: str) -> dict | None:
    q = """
    SELECT b.*, s.code AS scheme_code, s.name AS scheme_name, s.enabled AS scheme_enabled
    FROM zone_bindings b
    JOIN tier_schemes s ON s.id = b.scheme_id
    WHERE b.zone_code = ?
    """
    row = conn.execute(q, (zone_code,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["scheme_enabled"] = bool(d["scheme_enabled"])
    return d


def _validate_enabled(conn: sqlite3.Connection, scheme_id: int) -> None:
    scheme = conn.execute(
        "SELECT id, enabled FROM tier_schemes WHERE id=?", (scheme_id,)
    ).fetchone()
    if not scheme:
        raise LookupError(f"scheme {scheme_id} not found")
    if not scheme["enabled"]:
        raise SchemeDisabled(scheme_id)


def insert(conn: sqlite3.Connection, zone_code: str, scheme_id: int, note: str | None) -> None:
    """新增绑定。片区已绑 -> ZoneConflict（携带冲突方案标识）。"""
    _validate_enabled(conn, scheme_id)
    existing = get_by_zone(conn, zone_code)
    if existing:
        raise ZoneConflict(zone_code, existing["scheme_id"], existing["scheme_code"])
    try:
        conn.execute(
            "INSERT INTO zone_bindings(zone_code, scheme_id, note, created_at, updated_at) "
            "VALUES (?,?,?,datetime('now'),datetime('now'))",
            (zone_code, scheme_id, note),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        # 并发下唯一约束兜底：重新取一次冲突方案标识。
        racy = get_by_zone(conn, zone_code)
        raise ZoneConflict(
            zone_code,
            racy["scheme_id"] if racy else None,
            racy["scheme_code"] if racy else None,
        ) from e


def replace(conn: sqlite3.Connection, zone_code: str, scheme_id: int, note: str | None) -> bool:
    """改绑：已存在则整体替换，不存在则按 PUT 语义新建。返回是否新建。"""
    _validate_enabled(conn, scheme_id)
    existing = get_by_zone(conn, zone_code)
    if existing:
        conn.execute(
            "UPDATE zone_bindings SET scheme_id=?, note=?, updated_at=datetime('now') "
            "WHERE zone_code=?",
            (scheme_id, note, zone_code),
        )
        conn.commit()
        return False
    conn.execute(
        "INSERT INTO zone_bindings(zone_code, scheme_id, note, created_at, updated_at) "
        "VALUES (?,?,?,datetime('now'),datetime('now'))",
        (zone_code, scheme_id, note),
    )
    conn.commit()
    return True


def delete(conn: sqlite3.Connection, zone_code: str) -> bool:
    cur = conn.execute("DELETE FROM zone_bindings WHERE zone_code=?", (zone_code,))
    conn.commit()
    return cur.rowcount > 0
