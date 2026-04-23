from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


FeedbackType = Literal["like", "dislike"]
ExportFormat = Literal["csv", "json"]
DpoExportFormat = Literal["jsonl", "json", "csv"]


class FeedbackSubmitRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, max_length=128)
    message_id: str = Field(..., min_length=1, max_length=128)
    user_message: str = Field(..., min_length=1)
    ai_message: str = Field(..., min_length=1)
    feedback_type: FeedbackType
    route: str = Field(default="chat", min_length=1, max_length=128)
    model: str | None = Field(default=None, max_length=128)
    tool_calls: Any | None = None
    answer_source: Any | None = None


class FeedbackData(BaseModel):
    conversation_id: str
    message_id: str
    feedback_type: FeedbackType
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
