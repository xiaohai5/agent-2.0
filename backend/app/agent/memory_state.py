"""
Memory Agent 状态模型定义
定义分层记忆的状态结构，包括短期、中期、长期记忆
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


class MessageDict(TypedDict):
    """消息字典类型"""
    role: str
    content: str
    timestamp: float | None
    metadata: dict[str, Any] | None


@dataclass(slots=True)
class ToolCallSummary:
    """工具调用浓缩摘要"""
    tool_name: str
    action: str  # 做了什么
    key_params: dict[str, Any]  # 关键参数
    result_summary: str  # 结果摘要
    success: bool
    timestamp: float


@dataclass(slots=True)
class CompressedMessage:
    """压缩后的消息"""
    role: str
    compressed_content: str  # 压缩后的内容
    original_length: int  # 原始长度
    compressed_length: int  # 压缩后长度
    timestamp: float
    tool_calls: list[ToolCallSummary] = field(default_factory=list)


@dataclass(slots=True)
class LongTermSummary:
    """长期记忆摘要"""
    user_goal: str  # 用户当前阶段目标
    confirmed_conditions: list[str]  # 已确认条件
    user_preferences: dict[str, Any]  # 用户偏好与约束
    completed_steps: list[str]  # 已完成步骤
    pending_items: list[str]  # 未完成事项
    key_tool_conclusions: list[str]  # 关键工具调用结论
    important_context: str  # 后续仍可能影响回答的重要上下文
    summary_range: tuple[int, int]  # 摘要覆盖的消息范围 (start_idx, end_idx)
    created_at: float


@dataclass(slots=True)
class MemoryUpdateLog:
    """记忆更新日志"""
    action: str  # moved_to_compressed, moved_to_summary, compressed, summarized
    message_indices: list[int]  # 受影响的消息索引
    description: str  # 操作描述
    timestamp: float


class MemoryState(TypedDict):
    """Memory Agent 状态结构"""
    # 当前轮输入
    current_user_input: str

    # 最近 1-5 条完整记忆
    recent_full_memory: list[MessageDict]

    # 第 6-10 条压缩记忆
    mid_compressed_memory: list[CompressedMessage]

    # 超过 10 条的长期摘要
    long_term_summary: LongTermSummary | None

    # 最近工具调用结果
    latest_tool_results: list[ToolCallSummary]

    # 用户偏好（从历史中提取）
    user_preferences: dict[str, Any]

    # 已确认约束
    confirmed_constraints: list[str]

    # 待办事项
    pending_items: list[str]

    # 记忆更新日志
    memory_update_log: list[MemoryUpdateLog]

    # 元数据
    total_message_count: int  # 总消息数
    last_update_timestamp: float


class DialogState(TypedDict):
    """对话 Agent 状态结构"""
    # 当前用户输入
    current_input: str

    # Memory Agent 提供的记忆上下文
    memory_context: dict[str, Any]

    # 生成的回复
    generated_response: str

    # 本轮工具调用
    current_tool_calls: list[dict[str, Any]]


class CombinedState(TypedDict):
    """组合状态（用于 LangGraph）"""
    # 用户输入
    user_input: str
    user_id: int
    top_k: int

    # Memory Agent 状态
    memory_state: MemoryState

    # Dialog Agent 状态
    dialog_state: DialogState

    # 最终输出
    final_answer: str
    tool_agents_ready: bool
    status: str
