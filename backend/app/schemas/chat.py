from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)
    history: list[ChatMessage] = Field(default_factory=list)
    conversation_id: str | None = Field(default=None, max_length=128)


class ChatData(BaseModel):
    answer: str
    history: list[ChatMessage]
    status: Literal["completed"] = "completed"
    conversation_id: str | None = None
    route: str = "chat"
    model: str | None = None
    tool_calls: list | dict | None = None
    answer_source: list | dict | str | None = None
