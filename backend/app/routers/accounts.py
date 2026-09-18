from fastapi import APIRouter, HTTPException

from app.schemas.zones import AccountZoneUpdate
from app.services.billing_service import BillingService

router = APIRouter(tags=["accounts"])


@router.get("/accounts")
def list_accounts(zone: str | None = None):
    with BillingService() as svc:
        return {"items": svc.list_accounts(zone), "zones": svc.list_zones()}


@router.get("/accounts/{account_id}")
def get_account(account_id: int):
    with BillingService() as svc:
        row = svc.get_account(account_id)
        if not row:
            raise HTTPException(404, "account not found")
        readings = svc.readings_for_account(account_id)
        return {"account": row, "readings": readings}


@router.put("/accounts/{account_id}/zone")
def update_account_zone(account_id: int, body: AccountZoneUpdate):
    with BillingService() as svc:
        try:
            return {"account": svc.update_account_zone(account_id, body.zone_code)}
        except LookupError as e:
            raise HTTPException(404, str(e))


@router.get("/accounts/{account_id}/resolved-tiers")
def resolved_tiers(account_id: int):
    """按户解析本次测算使用的档表（无绑定回退全局，包内标记 fallback/路径）。"""
    with BillingService() as svc:
        try:
            return svc.resolved_for_account(account_id)
        except LookupError as e:
            raise HTTPException(404, str(e))
