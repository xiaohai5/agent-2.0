"""
Memory Agent 核心实现
负责历史消息的存储、分层、压缩、总结、提取与更新
"""
from __future__ import annotations

import time
from typing import Any

from langchain_openai import ChatOpenAI

from llm.llm import read_llm
from project_config import SETTINGS

from .memory_state import (
    CompressedMessage,
    LongTermSummary,
    MemoryState,
    MemoryUpdateLog,
    MessageDict,
    ToolCallSummary,
)


class MemoryAgent:
    """Memory Agent - 专门负责会话记忆管理"""

    def __init__(self) -> None:
        self._llm: ChatOpenAI | None = None

    def _get_llm(self) -> ChatOpenAI:
        """获取 LLM 实例"""
        if self._llm is None:
            read_llm()
            self._llm = ChatOpenAI(model=SETTINGS.llm_model, temperature=0.1)
        return self._llm

    def initialize_memory(self) -> MemoryState:
        """初始化空记忆状态"""
        return MemoryState(
            current_user_input="",
            recent_full_memory=[],
            mid_compressed_memory=[],
            long_term_summary=None,
            latest_tool_results=[],
            user_preferences={},
            confirmed_constraints=[],
            pending_items=[],
            memory_update_log=[],
            total_message_count=0,
            last_update_timestamp=time.time(),
        )

    async def compress_message(self, message: MessageDict) -> CompressedMessage:
        """压缩单条消息 - 保留关键信息，删除冗余"""
        llm = self._get_llm()
        prompt = f"""请压缩以下对话消息，遵循规则：
1. 不改变原意
2. 保留：用户需求、约束条件、时间地点、偏好、任务目标、重要结论
3. 删除：寒暄、重复确认、无效补充、格式性废话、重复解释
4. 如果是工具调用结果，只保留：做了什么、关键参数、结果、是否成功、关键数据

原始消息：
角色：{message['role']}
内容：{message['content']}

请直接输出压缩后的内容，不要添加任何解释："""

        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        compressed_content = str(response.content).strip()

        return CompressedMessage(
            role=message["role"],
            compressed_content=compressed_content,
            original_length=len(message["content"]),
            compressed_length=len(compressed_content),
            timestamp=message.get("timestamp", time.time()),
            tool_calls=[],
        )

    async def generate_long_term_summary(
        self,
        messages: list[MessageDict | CompressedMessage],
        start_idx: int,
        end_idx: int,
    ) -> LongTermSummary:
        """生成长期记忆摘要"""
        llm = self._get_llm()

        # 构建消息文本
        message_texts = []
        for i, msg in enumerate(messages):
            if isinstance(msg, CompressedMessage):
                content = msg.compressed_content
            else:
                content = msg["content"]
            message_texts.append(f"[{i}] {msg['role'] if isinstance(msg, dict) else msg.role}: {content}")

        messages_blob = "\n".join(message_texts)

        prompt = f"""请对以下历史对话生成结构化摘要，必须包含：

1. 用户当前阶段目标
2. 已确认条件（列表）
3. 用户偏好与约束（字典格式）
4. 已完成步骤（列表）
5. 未完成事项（列表）
6. 关键工具调用结论（列表）
7. 后续仍可能影响回答的重要上下文

历史对话：
{messages_blob}

请按以下 JSON 格式输出：
{{
  "user_goal": "...",
  "confirmed_conditions": ["...", "..."],
  "user_preferences": {{"key": "value"}},
  "completed_steps": ["...", "..."],
  "pending_items": ["...", "..."],
  "key_tool_conclusions": ["...", "..."],
  "important_context": "..."
}}"""

        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        result_text = str(response.content).strip()

        # 解析 JSON
        import json

        try:
            summary_data = json.loads(result_text)
        except json.JSONDecodeError:
            # 如果解析失败，使用默认值
            summary_data = {
                "user_goal": "未明确",
                "confirmed_conditions": [],
                "user_preferences": {},
                "completed_steps": [],
                "pending_items": [],
                "key_tool_conclusions": [],
                "important_context": result_text,
            }

        return LongTermSummary(
            user_goal=summary_data.get("user_goal", "未明确"),
            confirmed_conditions=summary_data.get("confirmed_conditions", []),
            user_preferences=summary_data.get("user_preferences", {}),
            completed_steps=summary_data.get("completed_steps", []),
            pending_items=summary_data.get("pending_items", []),
            key_tool_conclusions=summary_data.get("key_tool_conclusions", []),
            important_context=summary_data.get("important_context", ""),
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
        """更新记忆状态 - 每轮对话结束后调用"""
        current_time = time.time()

        # 1. 将新消息加入 recent_full_memory
        new_messages: list[MessageDict] = [
            MessageDict(
                role="user",
                content=new_user_message,
                timestamp=current_time,
                metadata=None,
            ),
            MessageDict(
                role="assistant",
                content=new_assistant_message,
                timestamp=current_time,
                metadata=None,
            ),
        ]

        memory_state["recent_full_memory"].extend(new_messages)
        memory_state["total_message_count"] += 2

        # 2. 处理工具调用
        if tool_calls:
            for tc in tool_calls:
                tool_summary = ToolCallSummary(
                    tool_name=tc.get("tool_name", "unknown"),
                    action=tc.get("action", ""),
                    key_params=tc.get("key_params", {}),
                    result_summary=tc.get("result_summary", ""),
                    success=tc.get("success", True),
                    timestamp=current_time,
                )
                memory_state["latest_tool_results"].append(tool_summary)

        # 3. 如果 recent_full_memory 超过 5 条，移动到 mid_compressed_memory
        if len(memory_state["recent_full_memory"]) > 5:
            messages_to_compress = memory_state["recent_full_memory"][:-5]
            memory_state["recent_full_memory"] = memory_state["recent_full_memory"][-5:]

            for msg in messages_to_compress:
                compressed = await self.compress_message(msg)
                memory_state["mid_compressed_memory"].append(compressed)

            memory_state["memory_update_log"].append(
                MemoryUpdateLog(
                    action="moved_to_compressed",
                    message_indices=list(range(len(messages_to_compress))),
                    description=f"将 {len(messages_to_compress)} 条消息移动到压缩记忆",
                    timestamp=current_time,
                )
            )

        # 4. 如果 mid_compressed_memory 超过 5 条，生成长期摘要
        if len(memory_state["mid_compressed_memory"]) > 5:
            messages_to_summarize = memory_state["mid_compressed_memory"][:-5]
            memory_state["mid_compressed_memory"] = memory_state["mid_compressed_memory"][-5:]

            # 生成长期摘要
            start_idx = 0
            end_idx = len(messages_to_summarize)
            summary = await self.generate_long_term_summary(
                messages_to_summarize,
                start_idx,
                end_idx,
            )

            # 如果已有长期摘要，合并
            if memory_state["long_term_summary"] is not None:
                # 这里可以实现更复杂的合并逻辑
                # 简单起见，直接替换
                memory_state["long_term_summary"] = summary
            else:
                memory_state["long_term_summary"] = summary

            memory_state["memory_update_log"].append(
                MemoryUpdateLog(
                    action="moved_to_summary",
                    message_indices=list(range(len(messages_to_summarize))),
                    description=f"将 {len(messages_to_summarize)} 条压缩消息生成长期摘要",
                    timestamp=current_time,
                )
            )

        memory_state["last_update_timestamp"] = current_time
        return memory_state

    def get_memory_context(self, memory_state: MemoryState) -> dict[str, Any]:
        """获取分层记忆上下文 - 供对话 Agent 使用"""
        return {
            "recent_full_memory": memory_state["recent_full_memory"],
            "mid_compressed_memory": [
                {
                    "role": msg.role,
                    "content": msg.compressed_content,
                    "timestamp": msg.timestamp,
                }
                for msg in memory_state["mid_compressed_memory"]
            ],
            "long_term_summary": (
                {
                    "user_goal": memory_state["long_term_summary"].user_goal,
                    "confirmed_conditions": memory_state["long_term_summary"].confirmed_conditions,
                    "user_preferences": memory_state["long_term_summary"].user_preferences,
                    "completed_steps": memory_state["long_term_summary"].completed_steps,
                    "pending_items": memory_state["long_term_summary"].pending_items,
                    "key_tool_conclusions": memory_state["long_term_summary"].key_tool_conclusions,
                    "important_context": memory_state["long_term_summary"].important_context,
                }
                if memory_state["long_term_summary"]
                else None
            ),
            "latest_tool_results": [
                {
                    "tool_name": tr.tool_name,
                    "action": tr.action,
                    "result_summary": tr.result_summary,
                    "success": tr.success,
                }
                for tr in memory_state["latest_tool_results"][-3:]  # 只保留最近 3 个
            ],
            "user_preferences": memory_state["user_preferences"],
            "confirmed_constraints": memory_state["confirmed_constraints"],
            "pending_items": memory_state["pending_items"],
        }
