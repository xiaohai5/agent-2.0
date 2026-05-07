from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PlanDayItem(BaseModel):
    time: str = ""
    endTime: str = ""
    type: str = "general"
    placeName: str = ""
    name: str = ""
    description: str = ""
    lng: Optional[float] = None
    lat: Optional[float] = None


class PlanDay(BaseModel):
    day: int
    title: str
    items: list[PlanDayItem] = Field(default_factory=list)
    routes: list[list[list[float]]] = Field(default_factory=list)  # polylines per day


class SavedPlanCreate(BaseModel):
    title: str
    days: list[PlanDay] = Field(default_factory=list)
    overview: str = ""
    source_message_id: Optional[str] = None


class SavedPlanData(BaseModel):
    id: int
    user_id: int
    title: str
    plan_data: dict
    source_message_id: Optional[str] = None
    overview: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SavedPlanListData(BaseModel):
    plans: list[SavedPlanData]


class RouteMarker(BaseModel):
    lng: float
    lat: float
    name: str
    type: str  # "start" | "end" | "waypoint" | "start_end"
    num: int = 0
    color: str = ""


class RouteSegment(BaseModel):
    polyline: list[list[float]] = Field(default_factory=list)
    color: str
    label: str
    from_name: str
    to_name: str
    label_lng: float
    label_lat: float


class RouteDayData(BaseModel):
    day: int
    title: str
    color: str
    polyline: list[list[float]] = Field(default_factory=list)
    markers: list[RouteMarker] = Field(default_factory=list)
    segments: list[RouteSegment] = Field(default_factory=list)
    chunked: bool = False


class RoutePlanData(BaseModel):
    plan_id: int
    title: str
    days: list[RouteDayData] = Field(default_factory=list)
