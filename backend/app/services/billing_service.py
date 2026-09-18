import sqlite3

from app.db import connect
from app.engines.peak_compare import compare_plain_vs_peak
from app.engines.tier_progressive import calc_bill
from app.repositories import accounts as accounts_repo
from app.repositories import readings as readings_repo
from app.repositories import runs as runs_repo
from app.repositories import settings as settings_repo
from app.repositories import tier_plans as plans_repo
from app.repositories import tiers as tiers_repo
from app.repositories import zone_bindings as bindings_repo


class AccountNotFound(Exception):
    pass


class PlanNotFound(Exception):
    pass


class BindingNotFound(Exception):
    pass


class ZoneBindingConflict(Exception):
    """同一片区已存在启用绑定时抛出，携带冲突方案标识。"""

    def __init__(self, zone_code: str, conflict: dict):
        self.zone_code = zone_code
        self.conflict = conflict
        super().__init__(f"zone {zone_code} already bound to plan {conflict.get('plan_id')}")

    def payload(self) -> dict:
        return {
            "error": "zone_binding_conflict",
            "zone_code": self.zone_code,
            "conflict_binding_id": self.conflict.get("id"),
            "conflict_plan_id": self.conflict.get("plan_id"),
            "conflict_plan_name": self.conflict.get("plan_name"),
        }


def _global_resolution(zone_code: str | None = None) -> dict:
    return {
        "zone_code": zone_code,
        "binding_id": None,
        "plan_id": None,
        "plan_name": None,
        "fallback": True,
        "source": "global_tiers",
    }


class BillingService:
    def __init__(self):
        self._conn = connect()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ---- accounts ----
    def list_accounts(self, zone_code: str | None = None):
        return accounts_repo.list_all(self._conn, zone_code)

    def get_account(self, account_id: int):
        return accounts_repo.get(self._conn, account_id)

    def update_account_zone(self, account_id: int, zone_code: str | None):
        if not accounts_repo.get(self._conn, account_id):
            raise AccountNotFound(account_id)
        accounts_repo.set_zone_code(self._conn, account_id, zone_code)
        return accounts_repo.get(self._conn, account_id)

    def list_zone_codes(self):
        return accounts_repo.list_zone_codes(self._conn)

    # ---- tiers / plans ----
    def list_tiers(self):
        return tiers_repo.list_ordered(self._conn)

    def list_plans(self):
        return plans_repo.list_all(self._conn)

    def create_plan(self, name: str, tiers: list[dict]):
        return plans_repo.create(self._conn, name, tiers)

    # ---- zone bindings ----
    def list_bindings(self):
        return bindings_repo.list_all(self._conn)

    def create_binding(self, zone_code: str, plan_id: int):
        if not plans_repo.get(self._conn, plan_id):
            raise PlanNotFound(plan_id)
        existing = bindings_repo.enabled_for_zone(self._conn, zone_code)
        if existing:
            raise ZoneBindingConflict(zone_code, existing)
        try:
            binding_id = bindings_repo.create(self._conn, zone_code, plan_id)
        except sqlite3.IntegrityError:
            raise ZoneBindingConflict(
                zone_code, bindings_repo.enabled_for_zone(self._conn, zone_code) or {}
            )
        return bindings_repo.get(self._conn, binding_id)

    def update_binding(
        self,
        binding_id: int,
        *,
        zone_code: str | None = None,
        plan_id: int | None = None,
        status: str | None = None,
    ):
        current = bindings_repo.get(self._conn, binding_id)
        if not current:
            raise BindingNotFound(binding_id)
        if plan_id is not None and not plans_repo.get(self._conn, plan_id):
            raise PlanNotFound(plan_id)
        new_zone = zone_code if zone_code is not None else current["zone_code"]
        new_status = status if status is not None else current["status"]
        if new_status == "enabled":
            existing = bindings_repo.enabled_for_zone(self._conn, new_zone)
            if existing and existing["id"] != binding_id:
                raise ZoneBindingConflict(new_zone, existing)
        try:
            bindings_repo.update(
                self._conn, binding_id, zone_code=zone_code, plan_id=plan_id, status=status
            )
        except sqlite3.IntegrityError:
            raise ZoneBindingConflict(
                new_zone, bindings_repo.enabled_for_zone(self._conn, new_zone) or {}
            )
        return bindings_repo.get(self._conn, binding_id)

    # ---- resolution ----
    def resolve_tiers_for_zone(self, zone_code: str | None) -> dict:
        """解析片区生效档表；无启用绑定回退全局 tiers 并标记 fallback。"""
        if zone_code:
            binding = bindings_repo.enabled_for_zone(self._conn, zone_code)
            if binding:
                return {
                    "resolution": {
                        "zone_code": zone_code,
                        "binding_id": binding["id"],
                        "plan_id": binding["plan_id"],
                        "plan_name": binding["plan_name"],
                        "fallback": False,
                        "source": "zone_binding",
                    },
                    "tiers": plans_repo.as_calc_rows(self._conn, binding["plan_id"]),
                }
        return {
            "resolution": _global_resolution(zone_code),
            "tiers": tiers_repo.as_calc_rows(self._conn),
        }

    def resolve_tiers_for_account(self, account_id: int) -> dict:
        account = accounts_repo.get(self._conn, account_id)
        if not account:
            raise AccountNotFound(account_id)
        resolved = self.resolve_tiers_for_zone(account.get("zone_code"))
        resolved["account"] = account
        return resolved

    # ---- readings / settings ----
    def list_readings(self):
        return readings_repo.list_all(self._conn)

    def readings_for_account(self, account_id: int):
        return readings_repo.for_account(self._conn, account_id)

    def settings_map(self):
        return settings_repo.get_map(self._conn)

    # ---- calc ----
    def run_bill(self, kwh: float, peak: bool, account_id: int | None, persist: bool):
        if account_id is not None:
            resolved = self.resolve_tiers_for_account(account_id)
        else:
            resolved = {
                "resolution": _global_resolution(),
                "tiers": tiers_repo.as_calc_rows(self._conn),
            }
        tiers = resolved["tiers"]
        resolution = resolved["resolution"]
        pf = settings_repo.peak_factor(self._conn)
        factor = pf if peak else 1.0
        result = calc_bill(kwh, tiers, factor)
        run_id = None
        if persist:
            run_id = runs_repo.insert(
                self._conn,
                "bill",
                {"kwh": kwh, "peak": peak, "account_id": account_id, "resolution": resolution},
                result,
                account_id,
            )
        return {"run_id": run_id, "resolution": resolution, **result}

    def run_compare(self, kwh: float, persist: bool):
        tiers = tiers_repo.as_calc_rows(self._conn)
        pf = settings_repo.peak_factor(self._conn)
        result = compare_plain_vs_peak(kwh, tiers, pf)
        run_id = None
        if persist:
            run_id = runs_repo.insert(self._conn, "compare", {"kwh": kwh}, result, None)
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
