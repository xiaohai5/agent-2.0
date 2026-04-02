from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TravelPlanLockItem(BaseModel):
    field_name: str
    field_type: str = "selection"
    field_value: Any = None
    source_message: str | None = None
    is_active: bool = True
    locked_at: datetime | None = None


class TravelPlanCard(BaseModel):
    id: int
    title: str
    status: str
    origin: str | None = None
    destination: str | None = None
    departure_date: str | None = None
    return_date: str | None = None
    travelers: int | None = None
    budget: str | None = None
    summary: str | None = None
    confirmed_at: datetime | None = None
    locked_item_count: int = 0


class TravelPlanDetail(BaseModel):
    id: int
    title: str
    status: str
    source: str
    origin: str | None = None
    destination: str | None = None
    departure_date: str | None = None
    return_date: str | None = None
    travelers: int | None = None
    budget: str | None = None
    plan_summary: str | None = None
    draft_data: dict[str, Any] = Field(default_factory=dict)
    locked_data: dict[str, Any] = Field(default_factory=dict)
    final_confirmed_data: dict[str, Any] = Field(default_factory=dict)
    confirmed_at: datetime | None = None
    locked_items: list[TravelPlanLockItem] = Field(default_factory=list)


class TravelPlanListResponse(BaseModel):
    items: list[TravelPlanCard] = Field(default_factory=list)


class TravelPlanConfirmRequest(BaseModel):
    final_payload: dict[str, Any] = Field(default_factory=dict)
