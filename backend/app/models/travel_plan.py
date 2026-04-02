from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models import Base


class TravelPlan(Base):
    __tablename__ = "travel_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="未命名出行计划")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft", index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="chat")
    origin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(255), nullable=True)
    departure_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    return_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    travelers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    budget: Mapped[str | None] = mapped_column(String(100), nullable=True)
    plan_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    locked_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    final_confirmed_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TravelPlanLockedItem(Base):
    __tablename__ = "travel_plan_locked_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("travel_plans.id"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    field_type: Mapped[str] = mapped_column(String(50), nullable=False, default="selection")
    field_value: Mapped[dict[str, Any] | list[Any] | str | int | float | bool | None] = mapped_column(JSON, nullable=True)
    source_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    locked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
