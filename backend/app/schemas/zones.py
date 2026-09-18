from pydantic import BaseModel, Field, field_validator


class TierIn(BaseModel):
    up_to: float | None = Field(default=None, ge=0)
    price: float = Field(gt=0)


class TierSchemeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_\-]+$")
    name: str = Field(min_length=1, max_length=64)
    tiers: list[TierIn] = Field(min_length=1)
    enabled: bool = True

    @field_validator("tiers")
    @classmethod
    def _check_tiers(cls, v: list[TierIn]) -> list[TierIn]:
        prev = -1.0
        for i, t in enumerate(v):
            if t.up_to is None:
                if i != len(v) - 1:
                    raise ValueError("只有最后一档可以不设上限(up_to=null)")
            else:
                if t.up_to <= prev:
                    raise ValueError("各档上限必须严格递增")
                prev = t.up_to
        return v


class TierSchemeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    tiers: list[TierIn] | None = Field(default=None, min_length=1)
    enabled: bool | None = None

    @field_validator("tiers")
    @classmethod
    def _check_tiers(cls, v):
        return TierSchemeCreate._check_tiers(v)


class ZoneBindingCreate(BaseModel):
    zone_code: str = Field(min_length=1, max_length=32)
    scheme_id: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=128)


class ZoneBindingReplace(BaseModel):
    """PUT 改绑：片区取自路径，请求体只需方案与备注。"""
    scheme_id: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=128)


class AccountZoneUpdate(BaseModel):
    zone_code: str | None = Field(default=None, max_length=32)
