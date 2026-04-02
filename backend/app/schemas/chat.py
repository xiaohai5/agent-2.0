from typing import Any, Literal

from pydantic import BaseModel, Field

from project_config import SETTINGS


class ChatMessage(BaseModel):
    role: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(
        default=SETTINGS.final_top_k,
        ge=1,
        le=20,
        description="Final number of retrieved chunks passed to the LLM.",
    )
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    history: list[ChatMessage]
    status: Literal["completed", "needs_confirmation"] = "completed"
    pending_confirmation: dict[str, Any] | None = None
    final_summary: dict[str, Any] | None = None
