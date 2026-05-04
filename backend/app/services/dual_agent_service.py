from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from project_config import SETTINGS
from backend.app.agent.dual_agent_workflow import DualAgentWorkflow
from backend.app.agent.memory_state import CompressedMessage, MemoryState, MemoryUpdateLog, ToolCallSummary
from backend.app.memory.redis_store import RedisShortTermMemoryStore


logger = logging.getLogger(__name__)


class DualAgentChatService:
    def __init__(self) -> None:
        skill_path = Path(__file__).resolve().parents[3] / "skills" / "travel-life-service-auto-router" / "SKILL.md"
        self.workflow = DualAgentWorkflow(skill_path=skill_path)
        self.short_memory_store = RedisShortTermMemoryStore()

    async def _get_short_memory(self, user_id: int, conversation_id: str | None) -> MemoryState | None:
        memory_dict = await self.short_memory_store.get(user_id, conversation_id)
        return self._normalize_memory_state(memory_dict) if memory_dict else None

    async def _save_short_memory(
        self,
        user_id: int,
        conversation_id: str | None,
        memory_state: MemoryState,
    ) -> None:
        await self.short_memory_store.set(user_id, conversation_id, memory_state)

    async def answer(
        self,
        user_id: int,
        question: str,
        top_k: int,
        history: list[dict[str, Any]],
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        memory_state = await self._get_short_memory(user_id, conversation_id)

        if memory_state is None and history:
            memory_state = await self._initialize_memory_from_history(history)

        answer, updated_memory = await self.workflow.run(
            user_input=question,
            user_id=user_id,
            top_k=top_k,
            memory_state=memory_state,
        )

        await self._save_short_memory(user_id, conversation_id, updated_memory)
        self._schedule_long_term_update(question, answer)

        return {
            "answer": answer,
            "history": self._build_history_from_memory(updated_memory),
            "status": "completed",
            "route": "chat",
            "model": SETTINGS.llm_model,
            "tool_calls": None,
            "answer_source": None,
        }

    async def answer_stream(
        self,
        user_id: int,
        question: str,
        top_k: int,
        history: list[dict[str, Any]],
        conversation_id: str | None = None,
    ):
        yield {"type": "status", "message": "loading_short_memory"}
        memory_state = await self._get_short_memory(user_id, conversation_id)

        if memory_state is None and history:
            yield {"type": "status", "message": "initializing_short_memory"}
            memory_state = await self._initialize_memory_from_history(history)

        yield {"type": "status", "message": "generating_answer"}
        async for event in self.workflow.run_stream(
            user_input=question,
            user_id=user_id,
            top_k=top_k,
            memory_state=memory_state,
        ):
            if event.get("type") == "chunk":
                yield event

            if event.get("type") == "done":
                final_memory = event.get("memory_state")
                answer = event.get("answer", "")
                if final_memory:
                    await self._save_short_memory(user_id, conversation_id, final_memory)
                    self._schedule_long_term_update(question, answer)

                yield {"type": "status", "message": "ready_to_render"}
                yield {
                    "type": "done",
                    "payload": {
                        "answer": answer,
                        "history": self._build_history_from_memory(final_memory) if final_memory else history,
                        "status": event.get("status", "completed"),
                        "route": "chat",
                        "model": SETTINGS.llm_model,
                        "tool_calls": None,
                        "answer_source": None,
                    },
                }

    async def _initialize_memory_from_history(self, history: list[dict[str, Any]]) -> MemoryState:
        memory_state = self.workflow.memory_agent.initialize_memory()

        for i in range(0, len(history), 2):
            if i + 1 < len(history):
                user_msg = history[i]
                assistant_msg = history[i + 1]

                memory_state = await self.workflow.memory_agent.update_memory(
                    memory_state=memory_state,
                    new_user_message=user_msg.get("content", ""),
                    new_assistant_message=assistant_msg.get("content", ""),
                    tool_calls=None,
                )

        return memory_state

    def _build_history_from_memory(self, memory_state: MemoryState) -> list[dict[str, Any]]:
        return [
            {
                "role": msg["role"],
                "content": msg["content"],
            }
            for msg in memory_state["recent_full_memory"]
        ]

    async def clear_user_memory(self, user_id: int, conversation_id: str | None = None) -> None:
        await self.short_memory_store.delete(user_id, conversation_id)

    def _schedule_long_term_update(self, question: str, answer: str) -> None:
        async def runner() -> None:
            try:
                await self.workflow.memory_agent.update_long_term_memory(question, answer)
            except Exception:
                logger.exception("Long-term memory update failed")

        asyncio.create_task(runner())

    def _normalize_memory_state(self, state: dict[str, Any]) -> MemoryState:
        memory_state = self.workflow.memory_agent.initialize_memory()
        memory_state.update(state)
        memory_state["mid_compressed_memory"] = [
            item
            if isinstance(item, CompressedMessage)
            else CompressedMessage(
                role=item.get("role", "memory"),
                compressed_content=item.get("compressed_content", item.get("content", "")),
                original_length=int(item.get("original_length", 0)),
                compressed_length=int(item.get("compressed_length", 0)),
                timestamp=float(item.get("timestamp", 0)),
                tool_calls=[],
            )
            for item in memory_state.get("mid_compressed_memory", [])
        ]
        memory_state["latest_tool_results"] = [
            item
            if isinstance(item, ToolCallSummary)
            else ToolCallSummary(
                tool_name=item.get("tool_name", "unknown"),
                action=item.get("action", ""),
                key_params=item.get("key_params", {}),
                result_summary=item.get("result_summary", ""),
                success=bool(item.get("success", True)),
                timestamp=float(item.get("timestamp", 0)),
            )
            for item in memory_state.get("latest_tool_results", [])
        ]
        memory_state["memory_update_log"] = [
            item
            if isinstance(item, MemoryUpdateLog)
            else MemoryUpdateLog(
                action=item.get("action", ""),
                message_indices=item.get("message_indices", []),
                description=item.get("description", ""),
                timestamp=float(item.get("timestamp", 0)),
            )
            for item in memory_state.get("memory_update_log", [])
        ]
        return memory_state


dual_agent_chat_service = DualAgentChatService()
