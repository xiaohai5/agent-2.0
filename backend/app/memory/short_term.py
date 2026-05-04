from __future__ import annotations

import time
from typing import Any

from backend.app.agent.memory_state import MessageDict


class ShortTermMemory:
    max_recent_messages = 8

    def add_turn(self, memory_state: dict[str, Any], user_message: str, assistant_message: str) -> None:
        now = time.time()
        memory_state.setdefault("recent_full_memory", []).extend(
            [
                MessageDict(role="user", content=user_message, timestamp=now, metadata=None),
                MessageDict(role="assistant", content=assistant_message, timestamp=now, metadata=None),
            ]
        )
        memory_state["total_message_count"] = int(memory_state.get("total_message_count", 0)) + 2
        self.trim(memory_state)

    def trim(self, memory_state: dict[str, Any]) -> None:
        recent = memory_state.setdefault("recent_full_memory", [])
        if len(recent) <= self.max_recent_messages:
            return

        moved = recent[:-self.max_recent_messages]
        memory_state["recent_full_memory"] = recent[-self.max_recent_messages:]
        summary = memory_state.get("session_summary", "").strip()
        moved_text = "\n".join(f"{msg['role']}: {msg['content']}" for msg in moved)
        memory_state["session_summary"] = f"{summary}\n{moved_text}".strip()

