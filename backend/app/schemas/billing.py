from typing import Literal

from pydantic import BaseModel, Field


class BillRequest(BaseModel):
    account_id: int | None = None
    kwh: float = Field(ge=0)
    peak: bool = False
    persist: bool = True


class CompareRequest(BaseModel):
    kwh: float = Field(ge=0)
    persist: bool = False


class CalcRunOut(BaseModel):
    id: int
    kind: str
    account_id: int | None
    input_json: str
    result_json: str
    created_at: str


class TierIn(BaseModel):
    up_to: float | None = None
    price: float = Field(gt=0)


class TierPlanCreate(BaseModel):
    name: str = Field(min_length=1)
    tiers: list[TierIn] = Field(min_length=1)


class ZoneBindingCreate(BaseModel):
    zone_code: str = Field(min_length=1)
    plan_id: int


class ZoneBindingUpdate(BaseModel):
    zone_code: str | None = Field(default=None, min_length=1)
    plan_id: int | None = None
    status: Literal["enabled", "disabled"] | None = None


class AccountZoneUpdate(BaseModel):
    zone_code: str | None = None
