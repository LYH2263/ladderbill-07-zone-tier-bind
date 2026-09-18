from fastapi import APIRouter, HTTPException

from app.schemas.zones import (
    AccountZoneUpdate,
    TierSchemeCreate,
    TierSchemeUpdate,
    ZoneBindingCreate,
    ZoneBindingReplace,
)
from app.services.billing_service import BillingService, SchemeDisabled, ZoneConflict

router = APIRouter(tags=["zones"])


# ---- 档位方案（完整档表）----
@router.get("/tier-schemes")
def list_schemes():
    with BillingService() as svc:
        return {"items": svc.list_schemes()}


@router.post("/tier-schemes", status_code=201)
def create_scheme(body: TierSchemeCreate):
    with BillingService() as svc:
        try:
            return svc.create_scheme(body.code, body.name, [t.model_dump() for t in body.tiers], body.enabled)
        except ValueError as e:
            raise HTTPException(status_code=409, detail={"error": str(e), "code": body.code})


@router.put("/tier-schemes/{scheme_id}")
def update_scheme(scheme_id: int, body: TierSchemeUpdate):
    with BillingService() as svc:
        try:
            return svc.update_scheme(
                scheme_id,
                body.name,
                [t.model_dump() for t in body.tiers] if body.tiers is not None else None,
                body.enabled,
            )
        except LookupError as e:
            raise HTTPException(404, str(e))


# ---- 片区 -> 方案绑定 ----
@router.get("/zone-bindings")
def list_bindings():
    with BillingService() as svc:
        return {"items": svc.list_bindings()}


@router.post("/zone-bindings", status_code=201)
def create_binding(body: ZoneBindingCreate):
    with BillingService() as svc:
        try:
            return svc.bind_zone(body.zone_code, body.scheme_id, body.note)
        except ZoneConflict as e:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": f"片区 {e.zone_code} 已绑定其它启用方案",
                    "zone_code": e.zone_code,
                    "conflict_scheme_id": e.conflict_scheme_id,
                    "conflict_scheme_code": e.conflict_scheme_code,
                },
            )
        except SchemeDisabled as e:
            raise HTTPException(400, detail={"error": "目标方案已停用，不能绑定", "scheme_id": e.scheme_id})
        except LookupError as e:
            raise HTTPException(404, str(e))


@router.put("/zone-bindings/{zone_code}")
def replace_binding(zone_code: str, body: ZoneBindingReplace):
    # 路径优先，body 里的 zone_code 仅为保持请求体自描述。
    with BillingService() as svc:
        try:
            return svc.replace_binding(zone_code, body.scheme_id, body.note)
        except SchemeDisabled as e:
            raise HTTPException(400, detail={"error": "目标方案已停用，不能绑定", "scheme_id": e.scheme_id})
        except LookupError as e:
            raise HTTPException(404, str(e))


@router.delete("/zone-bindings/{zone_code}", status_code=204)
def delete_binding(zone_code: str):
    with BillingService() as svc:
        try:
            svc.unbind_zone(zone_code)
        except LookupError as e:
            raise HTTPException(404, str(e))
