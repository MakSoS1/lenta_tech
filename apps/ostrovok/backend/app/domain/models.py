from datetime import date
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field


class TripIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: str | None = None
    destinations: list[str] = Field(default_factory=list, max_length=8)
    departure_date: date | None = None
    return_by: date | None = None
    nights: int = Field(default=7, ge=2, le=14)
    adults: int = Field(default=1, ge=1, le=8)
    children_ages: list[Annotated[int, Field(ge=0, le=17)]] = Field(
        default_factory=list, max_length=4
    )
    children_count: int = Field(default=0, ge=0, le=4)
    pet_requested: bool = False
    pet_kg: float | None = Field(default=None, ge=0.1, le=50)
    budget_rub: int | None = Field(default=None, ge=1000, le=5000000)
    max_travel_hours: float | None = Field(default=None, gt=0, le=96)
    transport: Literal["any", "flight", "train"] = "any"
    meal: Literal["any", "breakfast", "all_inclusive"] = "any"
    refundable: bool = False
    warm: bool = False
    rooms: int = Field(default=1, ge=1, le=4)
    hotel_preference: Literal["any", "center", "beach"] = "any"
    lock_transport: bool = False


class InputMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(default="", max_length=4000)
    patch: dict | None = None


class ChangeMessage(InputMessage):
    expected_version: int = Field(ge=1)


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str
    expected_version: int = Field(ge=1)


class VersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class Confirmation(VersionRequest):
    quote_id: str
    confirmed: bool
    total_minor: int = Field(ge=0)
