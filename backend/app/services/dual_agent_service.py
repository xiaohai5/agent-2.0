"""
双 Agent 聊天服务
集成 Memory Agent 和 Dialog Agent 的服务层
使用 MySQL 持久化记忆状态
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from project_config import SETTINGS
from backend.app.agent.dual_agent_workflow import DualAgentWorkflow
from backend.app.agent.memory_state import MemoryState
from backend.app.crued import user_memory as memory_crud


class DualAgentChatService:
    """双 Agent 聊天服务 - 使用 Memory Agent + Dialog Agent + MySQL"""

    def __init__(self) -> None:
        skill_path = Path(__file__).resolve().parents[3] / "skills" / "travel-life-service-auto-router" / "SKILL.md"
        self.workflow = DualAgentWorkflow(skill_path=skill_path)

    async def _get_user_memory(self, db: AsyncSession, user_id: int) -> MemoryState | None:
        """从 MySQL 获取用户的记忆状态"""
        memory_dict = await memory_crud.get_user_memory(db, user_id)
        return memory_dict if memory_dict else None

    async def _save_user_memory(self, db: AsyncSession, user_id: int, memory_state: MemoryState) -> None:
        """保存用户的记忆状态到 MySQL"""
        await memory_crud.save_user_memory(db, user_id, memory_state)

    async def answer(
        self,
        db: AsyncSession,
        user_id: int,
        question: str,
        top_k: int,
        history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """生成回答（非流式）"""
        memory_state = await self._get_user_memory(db, user_id)

        if memory_state is None and history:
            memory_state = await self._initialize_memory_from_history(history)

        answer, updated_memory = await self.workflow.run(
            user_input=question,
            user_id=user_id,
            top_k=top_k,
            memory_state=memory_state,
        )

        await self._save_user_memory(db, user_id, updated_memory)

        next_history = self._build_history_from_memory(updated_memory)

        return {
            "answer": answer,
            "history": next_history,
            "status": "completed",
            "route": "chat",
            "model": SETTINGS.llm_model,
            "tool_calls": None,
            "answer_source": None,
        }

    async def answer_stream(
        self,
        db: AsyncSession,
        user_id: int,
        question: str,
        top_k: int,
        history: list[dict[str, Any]]
    ):
        """生成回答（流式）"""
        yield {"type": "status", "message": "loading_memory"}
        memory_state = await self._get_user_memory(db, user_id)

        if memory_state is None and history:
            yield {"type": "status", "message": "initializing_memory"}
            memory_state = await self._initialize_memory_from_history(history)

        yield {"type": "status", "message": "generating_answer"}
        final_memory = None
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
                if final_memory:
                    yield {"type": "status", "message": "saving_memory"}
                    await self._save_user_memory(db, user_id, final_memory)

                next_history = self._build_history_from_memory(final_memory) if final_memory else history

                yield {"type": "status", "message": "ready_to_render"}
                yield {
                    "type": "done",
                    "payload": {
                        "answer": event.get("answer", ""),
                        "history": next_history,
                        "status": event.get("status", "completed"),
                        "route": "chat",
                        "model": SETTINGS.llm_model,
                        "tool_calls": None,
                        "answer_source": None,
                    },
                }

    async def _initialize_memory_from_history(self, history: list[dict[str, Any]]) -> MemoryState:
        """从历史消息初始化记忆状态"""
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
        """从记忆状态构建历史"""
        history = []

        for msg in memory_state["recent_full_memory"]:
            history.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        return history

    async def clear_user_memory(self, db: AsyncSession, user_id: int) -> None:
        """清空用户记忆"""
        await memory_crud.delete_user_memory(db, user_id)


dual_agent_chat_service = DualAgentChatService()
