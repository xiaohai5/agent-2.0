from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


class MessageDict(TypedDict):
    role: str
    content: str
    timestamp: float | None
    metadata: dict[str, Any] | None


@dataclass(slots=True)
class ToolCallSummary:
    tool_name: str
    action: str
    key_params: dict[str, Any]
    result_summary: str
    success: bool
    timestamp: float


@dataclass(slots=True)
class CompressedMessage:
    role: str
    compressed_content: str
    original_length: int
    compressed_length: int
    timestamp: float
    tool_calls: list[ToolCallSummary] = field(default_factory=list)


@dataclass(slots=True)
class LongTermSummary:
    user_goal: str
    confirmed_conditions: list[str]
    user_preferences: dict[str, Any]
    completed_steps: list[str]
    pending_items: list[str]
    key_tool_conclusions: list[str]
    important_context: str
    summary_range: tuple[int, int]
    created_at: float


@dataclass(slots=True)
class MemoryUpdateLog:
    action: str
    message_indices: list[int]
    description: str
    timestamp: float


class MemoryState(TypedDict):
    current_user_input: str
    session_summary: str
    current_task: str
    recent_full_memory: list[MessageDict]
    mid_compressed_memory: list[CompressedMessage]
    long_term_summary: LongTermSummary | None
    retrieved_long_term_memory: list[dict[str, Any]]
    last_long_term_updates: list[dict[str, Any]]
    latest_tool_results: list[ToolCallSummary]
    user_preferences: dict[str, Any]
    confirmed_constraints: list[str]
    pending_items: list[str]
    memory_update_log: list[MemoryUpdateLog]
    total_message_count: int
    last_update_timestamp: float


class DialogState(TypedDict):
    current_input: str
    memory_context: dict[str, Any]
    generated_response: str
    current_tool_calls: list[dict[str, Any]]


class CombinedState(TypedDict):
    user_input: str
    user_id: int
    top_k: int
    memory_state: MemoryState
    dialog_state: DialogState
    final_answer: str
    tool_agents_ready: bool
    status: str
