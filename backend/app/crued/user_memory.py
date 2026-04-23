"""
用户记忆 CRUD 操作
"""
from __future__ import annotations

import dataclasses
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agent.memory_state import CompressedMessage, LongTermSummary, MemoryUpdateLog, ToolCallSummary
from backend.app.models.user_memory import UserMemory


def _serialize_memory_state(obj: Any) -> Any:
    """递归将 dataclass 对象转换为可 JSON 序列化的字典"""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize_memory_state(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _serialize_memory_state(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_memory_state(i) for i in obj]
    if isinstance(obj, tuple):
        return [_serialize_memory_state(i) for i in obj]
    return obj


def _deserialize_memory_state(state: dict[str, Any]) -> dict[str, Any]:
    """将从数据库读取的纯字典还原为含 dataclass 对象的 MemoryState"""
    state["mid_compressed_memory"] = [
        CompressedMessage(
            role=m["role"],
            compressed_content=m["compressed_content"],
            original_length=m["original_length"],
            compressed_length=m["compressed_length"],
            timestamp=m["timestamp"],
            tool_calls=[
                ToolCallSummary(
                    tool_name=tc["tool_name"],
                    action=tc["action"],
                    key_params=tc["key_params"],
                    result_summary=tc["result_summary"],
                    success=tc["success"],
                    timestamp=tc["timestamp"],
                )
                for tc in m.get("tool_calls", [])
            ],
        )
        for m in state.get("mid_compressed_memory", [])
    ]

    raw_summary = state.get("long_term_summary")
    if raw_summary:
        summary_range = raw_summary.get("summary_range", [0, 0])
        state["long_term_summary"] = LongTermSummary(
            user_goal=raw_summary["user_goal"],
            confirmed_conditions=raw_summary["confirmed_conditions"],
            user_preferences=raw_summary["user_preferences"],
            completed_steps=raw_summary["completed_steps"],
            pending_items=raw_summary["pending_items"],
            key_tool_conclusions=raw_summary["key_tool_conclusions"],
            important_context=raw_summary["important_context"],
            summary_range=(summary_range[0], summary_range[1]),
            created_at=raw_summary["created_at"],
        )

    state["latest_tool_results"] = [
        ToolCallSummary(
            tool_name=tc["tool_name"],
            action=tc["action"],
            key_params=tc["key_params"],
            result_summary=tc["result_summary"],
            success=tc["success"],
            timestamp=tc["timestamp"],
        )
        for tc in state.get("latest_tool_results", [])
    ]

    state["memory_update_log"] = [
        MemoryUpdateLog(
            action=log["action"],
            message_indices=log["message_indices"],
            description=log["description"],
            timestamp=log["timestamp"],
        )
        for log in state.get("memory_update_log", [])
    ]

    return state


async def get_user_memory(db: AsyncSession, user_id: int) -> dict[str, Any] | None:
    """获取用户的记忆状态"""
    result = await db.execute(select(UserMemory).where(UserMemory.user_id == user_id))
    memory = result.scalar_one_or_none()
    if memory is None:
        return None
    return _deserialize_memory_state(dict(memory.memory_state))


async def save_user_memory(db: AsyncSession, user_id: int, memory_state: dict[str, Any]) -> None:
    """保存或更新用户的记忆状态"""
    serialized_state = _serialize_memory_state(memory_state)
    result = await db.execute(select(UserMemory).where(UserMemory.user_id == user_id))
    memory = result.scalar_one_or_none()

    if memory:
        memory.memory_state = serialized_state
    else:
        memory = UserMemory(user_id=user_id, memory_state=serialized_state)
        db.add(memory)

    await db.commit()


async def delete_user_memory(db: AsyncSession, user_id: int) -> None:
    """删除用户的记忆状态"""
    result = await db.execute(select(UserMemory).where(UserMemory.user_id == user_id))
    memory = result.scalar_one_or_none()

    if memory:
        await db.delete(memory)
        await db.commit()
