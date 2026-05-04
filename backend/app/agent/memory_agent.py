from __future__ import annotations

import time
from typing import Any

from backend.app.memory import MemoryManager

from .memory_state import (
    CompressedMessage,
    LongTermSummary,
    MemoryState,
    MemoryUpdateLog,
    MessageDict,
    ToolCallSummary,
)


class MemoryAgent:
    def __init__(self) -> None:
        self.manager = MemoryManager()

    def initialize_memory(self) -> MemoryState:
        return MemoryState(
            current_user_input="",
            session_summary="",
            current_task="",
            recent_full_memory=[],
            mid_compressed_memory=[],
            long_term_summary=None,
            retrieved_long_term_memory=[],
            last_long_term_updates=[],
            latest_tool_results=[],
            user_preferences={},
            confirmed_constraints=[],
            pending_items=[],
            memory_update_log=[],
            total_message_count=0,
            last_update_timestamp=time.time(),
        )

    async def compress_message(self, message: MessageDict) -> CompressedMessage:
        content = str(message["content"]).strip()
        compressed_content = content[:180] + ("..." if len(content) > 180 else "")
        return CompressedMessage(
            role=message["role"],
            compressed_content=compressed_content,
            original_length=len(content),
            compressed_length=len(compressed_content),
            timestamp=message.get("timestamp") or time.time(),
            tool_calls=[],
        )

    async def generate_long_term_summary(
        self,
        messages: list[MessageDict | CompressedMessage],
        start_idx: int,
        end_idx: int,
    ) -> LongTermSummary:
        contents: list[str] = []
        for msg in messages:
            if isinstance(msg, CompressedMessage):
                contents.append(msg.compressed_content)
            else:
                contents.append(msg["content"])
        important_context = "\n".join(contents)[-800:]
        return LongTermSummary(
            user_goal="",
            confirmed_conditions=[],
            user_preferences={},
            completed_steps=[],
            pending_items=[],
            key_tool_conclusions=[],
            important_context=important_context,
            summary_range=(start_idx, end_idx),
            created_at=time.time(),
        )

    async def update_memory(
        self,
        memory_state: MemoryState,
        new_user_message: str,
        new_assistant_message: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> MemoryState:
        current_time = time.time()

        if tool_calls:
            for tc in tool_calls:
                memory_state["latest_tool_results"].append(
                    ToolCallSummary(
                        tool_name=tc.get("tool_name", "unknown"),
                        action=tc.get("action", ""),
                        key_params=tc.get("key_params", {}),
                        result_summary=tc.get("result_summary", ""),
                        success=tc.get("success", True),
                        timestamp=current_time,
                    )
                )

        before_count = len(memory_state["recent_full_memory"])
        self.manager.update_after_response(memory_state, new_user_message, new_assistant_message)
        moved_count = max(0, before_count + 2 - len(memory_state["recent_full_memory"]))

        if moved_count:
            moved = memory_state["session_summary"].splitlines()[-moved_count:]
            for line in moved:
                role, _, content = line.partition(":")
                compressed = CompressedMessage(
                    role=role.strip() or "memory",
                    compressed_content=content.strip(),
                    original_length=len(content),
                    compressed_length=len(content.strip()),
                    timestamp=current_time,
                    tool_calls=[],
                )
                memory_state["mid_compressed_memory"].append(compressed)
            memory_state["mid_compressed_memory"] = memory_state["mid_compressed_memory"][-8:]
            memory_state["memory_update_log"].append(
                MemoryUpdateLog(
                    action="moved_to_session_summary",
                    message_indices=list(range(moved_count)),
                    description=f"Moved {moved_count} messages into short-term session summary",
                    timestamp=current_time,
                )
            )

        memory_state["last_update_timestamp"] = current_time
        return memory_state

    async def update_long_term_memory(self, user_message: str, assistant_message: str) -> list[dict[str, Any]]:
        return self.manager.update_long_term_from_turn(user_message, assistant_message)

    def get_memory_context(self, memory_state: MemoryState) -> dict[str, Any]:
        query = memory_state.get("current_user_input", "")
        context = self.manager.build_context(memory_state, query=query)
        context["mid_compressed_memory"] = [
            {
                "role": msg.role,
                "content": msg.compressed_content,
                "timestamp": msg.timestamp,
            }
            for msg in memory_state.get("mid_compressed_memory", [])
        ]
        context["latest_tool_results"] = [
            {
                "tool_name": item.tool_name,
                "action": item.action,
                "result_summary": item.result_summary,
                "success": item.success,
            }
            for item in memory_state.get("latest_tool_results", [])[-3:]
        ]
        context["long_term_summary"] = None
        context["user_preferences"] = memory_state.get("user_preferences", {})
        context["confirmed_constraints"] = memory_state.get("confirmed_constraints", [])
        context["pending_items"] = memory_state.get("pending_items", [])
        context["last_long_term_updates"] = memory_state.get("last_long_term_updates", [])
        return context
