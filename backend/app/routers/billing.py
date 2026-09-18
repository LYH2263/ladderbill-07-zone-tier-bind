from fastapi import APIRouter, HTTPException

from app.schemas.billing import BillRequest, CompareRequest
from app.services.billing_service import AccountNotFound, BillingService

router = APIRouter(tags=["billing"])


@router.post("/bill")
def post_bill(body: BillRequest):
    with BillingService() as svc:
        try:
            return svc.run_bill(body.kwh, body.peak, body.account_id, body.persist)
        except AccountNotFound:
            raise HTTPException(404, "account not found")


@router.post("/compare")
def post_compare(body: CompareRequest):
    with BillingService() as svc:
        return svc.run_compare(body.kwh, body.persist)
