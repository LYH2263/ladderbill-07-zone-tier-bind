import pytest

import app.db as db_module
from app import seed
from app.services.billing_service import (
    AccountNotFound,
    BillingService,
    ZoneBindingConflict,
)

GLOBAL_TIERS = [(180, 0.52), (260, 0.62), (None, 0.82)]
PLAN_TIERS = [(200, 0.55), (300, 0.65), (None, 0.88)]  # 种子“城区居民方案”，绑定 Z01


@pytest.fixture()
def svc(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test.db")
    seed.init_db()
    with BillingService() as s:
        yield s


def _bounds(tiers):
    return [(t["up_to"], t["price"]) for t in tiers]


def test_resolve_account_with_binding_uses_plan(svc):
    r = svc.resolve_tiers_for_account(1)  # 张家 Z01，种子已绑定城区居民方案
    assert r["resolution"]["fallback"] is False
    assert r["resolution"]["source"] == "zone_binding"
    assert r["resolution"]["zone_code"] == "Z01"
    assert r["resolution"]["plan_name"] == "城区居民方案"
    assert _bounds(r["tiers"]) == PLAN_TIERS


def test_resolve_account_without_binding_falls_back_to_global(svc):
    r = svc.resolve_tiers_for_account(2)  # 李家 Z02，无绑定
    assert r["resolution"]["fallback"] is True
    assert r["resolution"]["source"] == "global_tiers"
    assert r["resolution"]["zone_code"] == "Z02"
    assert r["resolution"]["plan_id"] is None
    assert _bounds(r["tiers"]) == GLOBAL_TIERS


def test_resolve_account_without_zone_falls_back(svc):
    svc.update_account_zone(1, None)
    r = svc.resolve_tiers_for_account(1)
    assert r["resolution"]["fallback"] is True
    assert r["resolution"]["zone_code"] is None
    assert _bounds(r["tiers"]) == GLOBAL_TIERS


def test_second_enabled_binding_same_zone_rejected(svc):
    plan_b = svc.create_plan("方案B", [{"up_to": None, "price": 1.0}])
    with pytest.raises(ZoneBindingConflict) as ei:
        svc.create_binding("Z01", plan_b["id"])
    payload = ei.value.payload()
    assert payload["error"] == "zone_binding_conflict"
    assert payload["zone_code"] == "Z01"
    assert payload["conflict_plan_name"] == "城区居民方案"
    assert payload["conflict_plan_id"] is not None


def test_disable_existing_binding_allows_new_one(svc):
    old = next(b for b in svc.list_bindings() if b["zone_code"] == "Z01")
    svc.update_binding(old["id"], status="disabled")
    plan_b = svc.create_plan("方案B", [{"up_to": None, "price": 1.0}])
    created = svc.create_binding("Z01", plan_b["id"])
    assert created["plan_id"] == plan_b["id"]
    r = svc.resolve_tiers_for_account(1)
    assert r["resolution"]["plan_id"] == plan_b["id"]
    assert r["resolution"]["fallback"] is False


def test_rebind_to_conflicting_zone_rejected(svc):
    plan_b = svc.create_plan("方案B", [{"up_to": None, "price": 1.0}])
    other = svc.create_binding("Z03", plan_b["id"])
    with pytest.raises(ZoneBindingConflict):
        # 把另一片区的启用绑定改到 Z01，视同重复绑定
        svc.update_binding(other["id"], zone_code="Z01")
    # 原绑定不受影响
    z01 = next(
        b for b in svc.list_bindings() if b["zone_code"] == "Z01" and b["status"] == "enabled"
    )
    assert z01["plan_name"] == "城区居民方案"


def test_run_bill_uses_resolved_plan_tiers(svc):
    r = svc.run_bill(100, False, 1, False)  # Z01 → 方案价 0.55
    assert r["total"] == 55.00
    assert r["resolution"]["fallback"] is False
    assert r["resolution"]["plan_name"] == "城区居民方案"
    assert r["resolution"]["zone_code"] == "Z01"


def test_run_bill_falls_back_to_global_tiers(svc):
    r = svc.run_bill(100, False, 2, False)  # Z02 无绑定 → 全局价 0.52
    assert r["total"] == 52.00
    assert r["resolution"]["fallback"] is True
    assert r["resolution"]["source"] == "global_tiers"


def test_run_bill_without_account_uses_global(svc):
    r = svc.run_bill(100, False, None, False)
    assert r["total"] == 52.00
    assert r["resolution"]["fallback"] is True
    assert r["resolution"]["zone_code"] is None


def test_run_bill_unknown_account_raises(svc):
    with pytest.raises(AccountNotFound):
        svc.run_bill(100, False, 999, False)
