from fastapi import APIRouter, HTTPException

from app.schemas.billing import TierPlanCreate, ZoneBindingCreate, ZoneBindingUpdate
from app.services.billing_service import (
    AccountNotFound,
    BillingService,
    BindingNotFound,
    PlanNotFound,
    ZoneBindingConflict,
)

router = APIRouter(tags=["zones"])


def _raise_mapped(exc: Exception):
    if isinstance(exc, ZoneBindingConflict):
        return HTTPException(409, detail=exc.payload())
    if isinstance(exc, (PlanNotFound, BindingNotFound, AccountNotFound)):
        return HTTPException(404, detail=str(exc))
    return exc


@router.get("/zones")
def list_zones():
    with BillingService() as svc:
        codes = set(svc.list_zone_codes())
        codes.update(b["zone_code"] for b in svc.list_bindings())
        return {"items": sorted(codes)}


@router.get("/tier-plans")
def list_plans():
    with BillingService() as svc:
        return {"items": svc.list_plans()}


@router.post("/tier-plans", status_code=201)
def create_plan(body: TierPlanCreate):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "plan name must not be blank")
    with BillingService() as svc:
        tiers = [t.model_dump() for t in body.tiers]
        return svc.create_plan(name, tiers)


@router.get("/zone-bindings")
def list_bindings():
    with BillingService() as svc:
        return {"items": svc.list_bindings()}


@router.post("/zone-bindings", status_code=201)
def create_binding(body: ZoneBindingCreate):
    zone_code = body.zone_code.strip()
    if not zone_code:
        raise HTTPException(422, "zone_code must not be blank")
    with BillingService() as svc:
        try:
            return svc.create_binding(zone_code, body.plan_id)
        except (ZoneBindingConflict, PlanNotFound) as exc:
            raise _raise_mapped(exc)


@router.put("/zone-bindings/{binding_id}")
def update_binding(binding_id: int, body: ZoneBindingUpdate):
    zone_code = body.zone_code.strip() if body.zone_code is not None else None
    if body.zone_code is not None and not zone_code:
        raise HTTPException(422, "zone_code must not be blank")
    with BillingService() as svc:
        try:
            return svc.update_binding(
                binding_id,
                zone_code=zone_code,
                plan_id=body.plan_id,
                status=body.status,
            )
        except (ZoneBindingConflict, PlanNotFound, BindingNotFound) as exc:
            raise _raise_mapped(exc)


@router.get("/accounts/{account_id}/tier-resolution")
def resolve_for_account(account_id: int):
    with BillingService() as svc:
        try:
            return svc.resolve_tiers_for_account(account_id)
        except AccountNotFound:
            raise HTTPException(404, "account not found")
