import json
import sqlite3

from app.db import connect
from app.engines.peak_compare import compare_plain_vs_peak
from app.engines.tier_progressive import calc_bill
from app.repositories import accounts as accounts_repo
from app.repositories import readings as readings_repo
from app.repositories import runs as runs_repo
from app.repositories import settings as settings_repo
from app.repositories import tier_schemes as schemes_repo
from app.repositories import tiers as tiers_repo
from app.repositories import zone_bindings as bindings_repo
from app.repositories.zone_bindings import SchemeDisabled, ZoneConflict

__all__ = ["BillingService", "ZoneConflict", "SchemeDisabled"]


class BillingService:
    def __init__(self):
        self._conn = connect()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ---- 基础数据 ----
    def list_accounts(self, zone_code: str | None = None):
        return accounts_repo.list_all(self._conn, zone_code)

    def get_account(self, account_id: int):
        return accounts_repo.get(self._conn, account_id)

    def update_account_zone(self, account_id: int, zone_code: str | None) -> dict:
        zone_code = (zone_code or "").strip() or None
        ok = accounts_repo.update_zone(self._conn, account_id, zone_code)
        if not ok:
            raise LookupError(f"account {account_id} not found")
        return accounts_repo.get(self._conn, account_id)

    def list_zones(self):
        return accounts_repo.list_zones(self._conn)

    def list_tiers(self):
        return tiers_repo.list_ordered(self._conn)

    def list_readings(self):
        return readings_repo.list_all(self._conn)

    def readings_for_account(self, account_id: int):
        return readings_repo.for_account(self._conn, account_id)

    def settings_map(self):
        return settings_repo.get_map(self._conn)

    # ---- 档位方案 ----
    def list_schemes(self):
        return schemes_repo.list_schemes(self._conn)

    def get_scheme(self, scheme_id: int):
        return schemes_repo.get(self._conn, scheme_id)

    def create_scheme(self, code: str, name: str, tiers: list[dict], enabled: bool) -> dict:
        try:
            sid = schemes_repo.create(self._conn, code.strip(), name.strip(), tiers, enabled)
        except sqlite3.IntegrityError as e:
            raise ValueError(f"scheme code {code!r} already exists") from e
        return schemes_repo.get(self._conn, sid)

    def update_scheme(self, scheme_id: int, name, tiers, enabled) -> dict:
        if not schemes_repo.get_raw(self._conn, scheme_id):
            raise LookupError(f"scheme {scheme_id} not found")
        schemes_repo.update(self._conn, scheme_id, name, tiers, enabled)
        return schemes_repo.get(self._conn, scheme_id)

    # ---- 片区绑定 ----
    def list_bindings(self):
        return bindings_repo.list_bindings(self._conn)

    def bind_zone(self, zone_code: str, scheme_id: int, note: str | None) -> dict:
        zone_code = zone_code.strip()
        bindings_repo.insert(self._conn, zone_code, scheme_id, note)
        return bindings_repo.get_by_zone(self._conn, zone_code)

    def replace_binding(self, zone_code: str, scheme_id: int, note: str | None) -> dict:
        zone_code = zone_code.strip()
        bindings_repo.replace(self._conn, zone_code, scheme_id, note)
        return bindings_repo.get_by_zone(self._conn, zone_code)

    def unbind_zone(self, zone_code: str) -> None:
        if not bindings_repo.delete(self._conn, zone_code.strip()):
            raise LookupError(f"binding for zone {zone_code!r} not found")

    # ---- 档表解析 ----
    def resolve_tiers(self, account_id: int | None = None) -> tuple[list[dict], dict]:
        """按户解析档表。

        解析顺序：户号 -> 片区代码 -> 启用绑定 -> 启用方案的完整档表；
        任一环节缺失（无片区 / 无绑定 / 方案已停用）则回退全局 tiers。
        返回 (calc_rows, resolution)。
        """
        account = None
        zone_code = None
        path = []
        if account_id is not None:
            account = accounts_repo.get(self._conn, account_id)
            path.append(f"account:{account_id}")
            if account:
                zone_code = account.get("zone_code")
                path.append(f"zone:{zone_code or '∅'}")
            else:
                path.append("account:not-found")
        else:
            path.append("account:none")

        fallback_reason = None
        binding = None
        if not zone_code:
            fallback_reason = "no_zone" if account is not None else "no_account"
            path.append("global:tiers")
        else:
            binding = bindings_repo.get_by_zone(self._conn, zone_code)
            if not binding:
                fallback_reason = "no_binding"
                path.append("binding:none")
                path.append("global:tiers")
            elif not binding["scheme_enabled"]:
                fallback_reason = "scheme_disabled"
                path.append(f"binding:scheme#{binding['scheme_id']}")
                path.append(f"scheme:{binding['scheme_code']}:disabled")
                path.append("global:tiers")
            else:
                path.append(f"binding:scheme#{binding['scheme_id']}")
                path.append(f"scheme:{binding['scheme_code']}")

        if fallback_reason is not None:
            tiers = tiers_repo.as_calc_rows(self._conn)
            resolution = {
                "zone_code": zone_code,
                "fallback": True,
                "fallback_reason": fallback_reason,
                "tier_source": "global",
                "scheme_id": binding["scheme_id"] if binding else None,
                "scheme_code": binding["scheme_code"] if binding else None,
                "resolved_path": path,
            }
            return tiers, resolution

        tiers = schemes_repo.as_calc_rows(self._conn, binding["scheme_id"])
        resolution = {
            "zone_code": zone_code,
            "fallback": False,
            "fallback_reason": None,
            "tier_source": "scheme",
            "scheme_id": binding["scheme_id"],
            "scheme_code": binding["scheme_code"],
            "resolved_path": path,
        }
        return tiers, resolution

    def resolved_for_account(self, account_id: int) -> dict:
        account = accounts_repo.get(self._conn, account_id)
        if not account:
            raise LookupError(f"account {account_id} not found")
        tiers, resolution = self.resolve_tiers(account_id)
        return {"account": account, "tiers": tiers, "resolution": resolution}

    # ---- 测算（走解析后的档表）----
    def run_bill(self, kwh: float, peak: bool, account_id: int | None, persist: bool):
        tiers, resolution = self.resolve_tiers(account_id)
        pf = settings_repo.peak_factor(self._conn)
        factor = pf if peak else 1.0
        result = calc_bill(kwh, tiers, factor)
        result["resolution"] = resolution
        run_id = None
        if persist:
            run_id = runs_repo.insert(
                self._conn,
                "bill",
                {"kwh": kwh, "peak": peak, "account_id": account_id},
                result,
                account_id,
            )
        return {"run_id": run_id, **result}

    def run_compare(self, kwh: float, persist: bool, account_id: int | None = None):
        tiers, resolution = self.resolve_tiers(account_id)
        pf = settings_repo.peak_factor(self._conn)
        result = compare_plain_vs_peak(kwh, tiers, pf)
        result["resolution"] = resolution
        run_id = None
        if persist:
            run_id = runs_repo.insert(
                self._conn, "compare",
                {"kwh": kwh, "account_id": account_id},
                result,
                account_id,
            )
        return {"run_id": run_id, **result}

    def list_history(self, limit: int = 50):
        return runs_repo.list_recent(self._conn, limit)

    def get_run(self, run_id: int):
        return runs_repo.get(self._conn, run_id)

    def dashboard_stats(self):
        accounts = accounts_repo.list_all(self._conn)
        readings = readings_repo.list_all(self._conn)
        clean = [a for a in accounts if "种子" not in a.get("name", "")]
        dirty = [a for a in accounts if "种子" in a.get("name", "")]
        return {
            "account_count": len(accounts),
            "reading_count": len(readings),
            "clean_accounts": len(clean),
            "dirty_accounts": len(dirty),
            "recent_runs": len(runs_repo.list_recent(self._conn, 5)),
        }
