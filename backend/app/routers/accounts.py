from fastapi import APIRouter, HTTPException

from app.schemas.billing import AccountZoneUpdate
from app.services.billing_service import AccountNotFound, BillingService

router = APIRouter(tags=["accounts"])


@router.get("/accounts")
def list_accounts(zone_code: str | None = None):
    with BillingService() as svc:
        return {"items": svc.list_accounts(zone_code)}


@router.get("/accounts/{account_id}")
def get_account(account_id: int):
    with BillingService() as svc:
        row = svc.get_account(account_id)
        if not row:
            raise HTTPException(404, "account not found")
        readings = svc.readings_for_account(account_id)
        return {"account": row, "readings": readings}


@router.patch("/accounts/{account_id}")
def update_account_zone(account_id: int, body: AccountZoneUpdate):
    with BillingService() as svc:
        try:
            zone = body.zone_code.strip() if body.zone_code else None
            return svc.update_account_zone(account_id, zone)
        except AccountNotFound:
            raise HTTPException(404, "account not found")
