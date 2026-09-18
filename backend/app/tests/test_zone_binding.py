import pytest

from app import seed
from app.repositories import zone_bindings as bindings_repo
from app.repositories.zone_bindings import SchemeDisabled, ZoneConflict
from app.services.billing_service import BillingService


@pytest.fixture()
def svc(monkeypatch, tmp_path):
    monkeypatch.setattr("app.db.DB_PATH", tmp_path / "test.db")
    seed.init_db()
    with BillingService() as s:
        yield s


def test_accounts_seeded_with_zones(svc):
    a1 = svc.get_account(1)
    assert a1["zone_code"] == "Z-A"
    assert svc.get_account(2)["zone_code"] == "Z-B"


def test_resolve_bound_zone_uses_scheme(svc):
    tiers, res = svc.resolve_tiers(1)
    assert res["fallback"] is False
    assert res["zone_code"] == "Z-A"
    assert res["scheme_code"] == "SCH-ZA"
    assert res["tier_source"] == "scheme"
    assert tiers == [
        {"up_to": 200.0, "price": 0.54},
        {"up_to": 300.0, "price": 0.65},
        {"up_to": None, "price": 0.88},
    ]
    assert res["resolved_path"] == [
        "account:1", "zone:Z-A", "binding:scheme#1", "scheme:SCH-ZA"
    ]


def test_resolve_unbound_zone_falls_back_to_global(svc):
    tiers, res = svc.resolve_tiers(2)
    assert res["fallback"] is True
    assert res["fallback_reason"] == "no_binding"
    assert res["zone_code"] == "Z-B"
    assert res["tier_source"] == "global"
    assert tiers == [
        {"up_to": 180.0, "price": 0.52},
        {"up_to": 260.0, "price": 0.62},
        {"up_to": None, "price": 0.82},
    ]
    assert res["resolved_path"][-1] == "global:tiers"


def test_resolve_account_without_zone_falls_back(svc):
    acc = svc.update_account_zone(2, None)
    assert acc["zone_code"] is None
    _, res = svc.resolve_tiers(2)
    assert res["fallback"] is True
    assert res["fallback_reason"] == "no_zone"


def test_resolve_without_account_falls_back(svc):
    tiers, res = svc.resolve_tiers(None)
    assert res["fallback"] is True
    assert res["fallback_reason"] == "no_account"
    assert res["zone_code"] is None
    assert len(tiers) == 3


def test_duplicate_binding_conflict_carries_scheme_id(svc):
    other = svc.create_scheme(
        "SCH-OTHER", "另一套", [{"up_to": 100, "price": 0.5}, {"up_to": None, "price": 0.9}], True
    )
    with pytest.raises(ZoneConflict) as ei:
        svc.bind_zone("Z-A", other["id"], "重复绑定")
    assert ei.value.conflict_scheme_id == 1
    assert ei.value.conflict_scheme_code == "SCH-ZA"
    # 原绑定不受影响
    assert svc.list_bindings()[0]["scheme_code"] == "SCH-ZA"


def test_put_rebind_succeeds(svc):
    other = svc.create_scheme(
        "SCH-OTHER", "另一套", [{"up_to": 100, "price": 0.5}, {"up_to": None, "price": 0.9}], True
    )
    b = svc.replace_binding("Z-A", other["id"], "改绑")
    assert b["scheme_id"] == other["id"]
    _, res = svc.resolve_tiers(1)
    assert res["scheme_code"] == "SCH-OTHER"
    assert res["fallback"] is False


def test_bind_disabled_scheme_rejected(svc):
    sid = svc.list_schemes()[0]["id"]
    svc.update_scheme(sid, None, None, False)
    with pytest.raises(SchemeDisabled):
        svc.replace_binding("Z-A", sid, None)


def test_disabling_bound_scheme_forces_fallback(svc):
    sid = svc.list_schemes()[0]["id"]
    svc.update_scheme(sid, None, None, False)
    tiers, res = svc.resolve_tiers(1)
    assert res["fallback"] is True
    assert res["fallback_reason"] == "scheme_disabled"
    assert res["scheme_code"] == "SCH-ZA"
    assert tiers[0]["price"] == 0.52  # 回退全局


def test_bill_uses_resolved_scheme_tiers(svc):
    # Z-A 首档 200kWh @0.54：120 * 0.54 = 64.8（全局档表为 62.4）
    r = svc.run_bill(120, False, 1, False)
    assert r["total"] == 64.8
    assert r["resolution"]["fallback"] is False
    assert r["resolution"]["scheme_code"] == "SCH-ZA"


def test_bill_fallback_account_uses_global(svc):
    # Z-B 无绑定：120 * 0.52 = 62.4
    r = svc.run_bill(120, False, 2, False)
    assert r["total"] == 62.4
    assert r["resolution"]["fallback"] is True
    assert r["resolution"]["zone_code"] == "Z-B"


def test_compare_uses_resolved_scheme_tiers(svc):
    r = svc.run_compare(120, False, 1)
    assert r["resolution"]["scheme_code"] == "SCH-ZA"
    assert r["plain_total"] == 64.8


def test_scheme_tiers_replace(svc):
    sid = svc.list_schemes()[0]["id"]
    updated = svc.update_scheme(
        sid, "改名", [{"up_to": 230, "price": 0.6}, {"up_to": None, "price": 0.95}], None
    )
    assert updated["name"] == "改名"
    assert updated["tiers"][0] == {"up_to": 230.0, "price": 0.6, "sort_order": 1}


def test_unbind_then_fallback(svc):
    svc.unbind_zone("Z-A")
    _, res = svc.resolve_tiers(1)
    assert res["fallback"] is True
    assert res["fallback_reason"] == "no_binding"


def test_filter_accounts_by_zone(svc):
    assert [a["id"] for a in svc.list_accounts("Z-A")] == [1]
    assert [a["id"] for a in svc.list_accounts("Z-B")] == [2]
