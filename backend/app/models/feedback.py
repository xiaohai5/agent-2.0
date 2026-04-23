from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models import Base


class MessageFeedback(Base):
    __tablename__ = "message_feedback"
    __table_args__ = (
        UniqueConstraint("user_id", "message_id", name="uq_message_feedback_user_message"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    ai_message: Mapped[str] = mapped_column(Text, nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    route: Mapped[str] = mapped_column(String(128), nullable=False, default="chat")
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_calls: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    answer_source: Mapped[dict | list | str | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
