from __future__ import annotations

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models import Base


class SavedPlan(Base):
    __tablename__ = "saved_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
