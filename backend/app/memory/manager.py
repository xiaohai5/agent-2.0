from __future__ import annotations

from typing import Any

from .extractor import LongTermMemoryExtractor
from .long_term import LongTermMemoryStore
from .retriever import MarkdownMemoryRetriever
from .short_term import ShortTermMemory


class MemoryManager:
    def __init__(self) -> None:
        self.store = LongTermMemoryStore()
        self.retriever = MarkdownMemoryRetriever(self.store)
        self.extractor = LongTermMemoryExtractor()
        self.short_term = ShortTermMemory()

    def build_context(self, memory_state: dict[str, Any], query: str) -> dict[str, Any]:
        retrieved = self.retriever.retrieve(self._build_query(memory_state, query), top_k=4)
        serialized = [
            {
                "file": item.file,
                "section": item.section,
                "content": item.content,
                "score": item.score,
            }
            for item in retrieved
        ]
        memory_state["retrieved_long_term_memory"] = serialized

        return {
            "recent_full_memory": memory_state.get("recent_full_memory", []),
            "session_summary": memory_state.get("session_summary", ""),
            "current_task": memory_state.get("current_task", ""),
            "retrieved_long_term_memory": serialized,
            "latest_tool_results": memory_state.get("latest_tool_results", [])[-3:],
        }

    def update_after_response(
        self,
        memory_state: dict[str, Any],
        user_message: str,
        assistant_message: str,
    ) -> list[dict[str, Any]]:
        self.short_term.add_turn(memory_state, user_message, assistant_message)
        memory_state["last_long_term_updates"] = []
        return []

    def update_long_term_from_turn(
        self,
        user_message: str,
        assistant_message: str,
    ) -> list[dict[str, Any]]:
        updates = self.extractor.extract(user_message, assistant_message)
        applied: list[dict[str, Any]] = []
        for update in updates:
            if self.store.apply_update(update):
                applied.append(
                    {
                        "action": update.action,
                        "file": update.file,
                        "section": update.section,
                        "content": update.content,
                    }
                )
        return applied

    @staticmethod
    def _build_query(memory_state: dict[str, Any], query: str) -> str:
        parts = [query, memory_state.get("session_summary", ""), memory_state.get("current_task", "")]
        for message in memory_state.get("recent_full_memory", [])[-4:]:
            parts.append(str(message.get("content", "")))
        return "\n".join(part for part in parts if part)
