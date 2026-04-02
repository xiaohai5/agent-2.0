from __future__ import annotations

import asyncio
import contextvars
import json
import re
from typing import Any, Literal, TypedDict

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from llm.llm import read_llm
from project_config import SETTINGS


RouteType = Literal["ticket", "rag", "roadmap", "other"]
ChatStatus = Literal["completed", "needs_confirmation"]
InheritMode = Literal["none", "reference_only", "task_continue"]

_TICKET_KEYWORDS = {
    "12306",
    "火车票",
    "高铁票",
    "车票",
    "余票",
    "车次",
    "改签",
    "退票",
    "购票",
    "抢票",
    "出发站",
    "到达站",
}
_ROADMAP_KEYWORDS = {
    "路线",
    "导航",
    "地图",
    "高德",
    "天气",
    "路况",
    "附近",
    "距离",
    "位置",
    "坐标",
    "打车",
    "公交",
    "地铁",
    "驾车",
    "景点",
    "景区",
    "游玩",
    "旅游",
    "旅行",
    "一日游",
    "两日游",
    "打卡",
    "行程",
    "攻略",
    "住宿",
    "住哪里",
    "酒店",
    "宾馆",
    "民宿",
    "旅店",
    "客栈",
    "青旅",
}
_RAG_KEYWORDS = {
    "铁路购票",
    "车站乘车",
    "地图导航",
    "跨城出行",
    "出行应急",
    "出行建议",
    "城市公共交通",
    "客服对话",
    "12306",
    "退票规则",
    "改签规则",
    "候补规则",
    "购票规则",
    "乘车规定",
    "进站规定",
    "实名制",
    "报销凭证",
}
_RAG_RULE_KEYWORDS = {
    "规则",
    "规定",
    "政策",
    "条件",
    "限制",
    "要求",
    "说明",
    "流程",
    "办法",
    "怎么退",
    "如何退",
    "怎么改签",
    "如何改签",
    "能不能退",
    "能不能改签",
    "可以退吗",
    "可以改吗",
    "退票",
    "改签",
    "候补",
    "学生票",
    "儿童票",
    "报销",
    "报销凭证",
    "退改",
    "手续费",
    "发车前",
    "开车后",
    "多久之前",
}
_CONFIRM_ACTION_KEYWORDS = {
    "订",
    "预订",
    "预定",
    "预约",
    "订房",
    "订票",
    "购票",
    "买",
    "购买",
    "出票",
    "抢票",
    "下单",
}
_CONFIRM_REPLY_KEYWORDS = {
    "确认",
    "确定",
    "同意",
    "继续",
    "可以",
    "好的",
    "好",
    "行",
    "没问题",
    "yes",
    "ok",
    "okay",
    "sure",
}
_HOTEL_OBJECT_KEYWORDS = {"酒店", "宾馆", "民宿"}
_SPECIFIC_TICKET_OBJECT_KEYWORDS = {"车票", "火车票", "高铁票", "机票", "门票", "船票"}
_SPECIFIC_TICKET_DETAIL_KEYWORDS = {
    "12306",
    "车次",
    "出发站",
    "到达站",
    "从",
    "到",
    "明天",
    "后天",
    "今天",
    "上午",
    "下午",
    "晚上",
    "几点",
    "一等座",
    "二等座",
    "头等舱",
    "经济舱",
}
_TRAVEL_PLAN_KEYWORDS = {
    "旅行",
    "旅游",
    "行程",
    "攻略",
    "出游",
    "出行计划",
    "酒店",
    "民宿",
    "景点",
    "路线",
    "高铁",
    "火车票",
    "机票",
}

FIELD_LABELS = {
    "origin": "出发地",
    "destination": "目的地",
    "departure_date": "出发日期",
    "return_date": "返程日期",
    "travelers": "出行人数",
    "budget": "预算",
    "title": "计划标题",
    "route": "计划类型",
    "plan_summary": "行程摘要",
    "ticket_option": "已锁定车票",
    "hotel_option": "已锁定住宿",
    "plan_version": "已锁定方案",
    "route_option": "已锁定路线",
    "scenic_option": "已锁定景点",
}


class ChatGraphState(TypedDict, total=False):
    question: str
    effective_question: str
    rewritten_question: str
    context_summary: str
    detected_needs: list[str]
    prior_routes: list[str]
    history: list[dict[str, Any]]
    raw_history: list[dict[str, Any]]
    top_k: int
    user_id: int
    route: RouteType
    status: ChatStatus
    confirmed: bool
    requires_confirmation: bool
    pending_confirmation: dict[str, Any]
    previous_task_summary: dict[str, Any]
    inherit_mode: InheritMode
    carry_fields: list[str]
    inherit_reason: str
    inherited_context: dict[str, Any]
    recommendation_memory: dict[str, Any]
    recent_history_summary: str
    other_history: list[dict[str, Any]]
    other_memory_summary: str
    draft_answer: str
    internal_answer: str
    answer: str
    answer_source: str
    verification: dict[str, Any]
    final_summary: dict[str, Any]
    carry_context: bool
    current_plan_id: int | None
    plan_draft: dict[str, Any]
    locked_fields: dict[str, Any]
    candidate_options: list[dict[str, Any]]
    selection_action: str
    selection_target: dict[str, Any]
    ready_for_final_confirmation: bool
    final_confirmation_payload: dict[str, Any]
    plan_confirmation_completed: bool
    primary_intent: str
    subtask_routes: list[str]
    task_outputs: dict[str, dict[str, Any]]
    image_items: list[dict[str, str]]


_STREAM_QUEUE: contextvars.ContextVar[asyncio.Queue[dict[str, Any]] | None] = contextvars.ContextVar(
    "chat_graph_stream_queue",
    default=None,
)

HISTORY_WINDOW_SIZE = 10


def set_stream_queue(queue: asyncio.Queue[dict[str, Any]] | None):
    return _STREAM_QUEUE.set(queue)


def reset_stream_queue(token: contextvars.Token[asyncio.Queue[dict[str, Any]] | None]) -> None:
    _STREAM_QUEUE.reset(token)


def _build_llm(temperature: float = 0) -> ChatOpenAI:
    read_llm()
    return ChatOpenAI(model=SETTINGS.llm_model, temperature=temperature)


def _emit_stream_event(event_type: str, **data: Any) -> None:
    queue = _STREAM_QUEUE.get()
    if queue is None:
        return
    queue.put_nowait({"type": event_type, **data})


def _emit_node_start(node: str, message: str = "") -> None:
    _emit_stream_event("node_start", node=node, message=message)


def _emit_node_complete(node: str, message: str = "", **data: Any) -> None:
    _emit_stream_event("node_complete", node=node, message=message, **data)


def _emit_node_error(node: str, error: str) -> None:
    _emit_stream_event("node_error", node=node, error=error)


def _coerce_stream_chunk_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
            else:
                text = str(getattr(item, "text", item)).strip()
            if text:
                parts.append(text)
        return "".join(parts)
    return str(content or "")


def _strip_think_tags(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.DOTALL).strip()


def _normalize_history(history: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in history or []:
        role = str(item.get("role", "")).strip().lower() or "user"
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        normalized_item: dict[str, Any] = {"role": role, "content": content}
        metadata = item.get("metadata")
        if isinstance(metadata, dict) and metadata:
            normalized_item["metadata"] = metadata
        normalized.append(normalized_item)
    return normalized


def _clone_history_items(history: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    cloned: list[dict[str, Any]] = []
    for item in _normalize_history(history):
        cloned_item: dict[str, Any] = {
            "role": str(item.get("role", "")).strip() or "user",
            "content": str(item.get("content", "")).strip(),
        }
        metadata = item.get("metadata")
        if isinstance(metadata, dict) and metadata:
            cloned_item["metadata"] = dict(metadata)
        cloned.append(cloned_item)
    return cloned


def _extract_history_digest(history: list[dict[str, Any]] | None) -> str:
    for item in history or []:
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            continue
        digest = str(metadata.get("history_digest", "")).strip()
        if digest:
            return digest
    return ""


def _format_history_messages(
    history: list[dict[str, Any]] | None,
    *,
    max_chars_per_message: int = 240,
) -> str:
    lines: list[str] = []
    for item in _normalize_history(history):
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        if len(content) > max_chars_per_message:
            content = content[: max_chars_per_message - 1].rstrip() + "…"
        role_label = "用户" if role == "user" else "助手"
        lines.append(f"{role_label}: {content}")
    return "\n".join(lines)


def _summarize_history_overflow(
    history: list[dict[str, Any]] | None,
    *,
    previous_digest: str = "",
) -> str:
    formatted_history = _format_history_messages(history, max_chars_per_message=200)
    previous_digest = str(previous_digest).strip()
    if not formatted_history:
        return previous_digest

    try:
        llm = _build_llm()
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你负责压缩对话历史。请保留用户目标、约束条件、已确认结论、待确认事项和关键上下文，输出一段简洁中文摘要，不要使用 JSON。",
                ),
                (
                    "user",
                    "已有历史摘要：\n{previous_digest}\n\n"
                    "需要新压缩的更早对话：\n{history_text}\n\n"
                    "请输出新的合并摘要，控制在 220 字以内，缺失内容不要编造。",
                ),
            ]
        )
        response = llm.invoke(
            prompt.format_messages(
                previous_digest=previous_digest or "无",
                history_text=formatted_history,
            )
        )
        summary = _strip_think_tags(str(getattr(response, "content", response))).strip()
        if summary:
            return summary
    except Exception:
        pass

    fallback_parts = [part for part in [previous_digest, formatted_history] if part]
    fallback = "\n".join(fallback_parts).strip()
    if len(fallback) > 220:
        fallback = fallback[:219].rstrip() + "…"
    return fallback


def _compress_history_for_context(
    history: list[dict[str, Any]] | None,
    *,
    keep_last: int = HISTORY_WINDOW_SIZE,
) -> tuple[list[dict[str, Any]], str]:
    normalized = _clone_history_items(history)
    if not normalized:
        return [], ""

    previous_digest = _extract_history_digest(normalized)
    for item in normalized:
        metadata = item.get("metadata")
        if isinstance(metadata, dict) and "history_digest" in metadata:
            cleaned = dict(metadata)
            cleaned.pop("history_digest", None)
            if cleaned:
                item["metadata"] = cleaned
            else:
                item.pop("metadata", None)

    overflow_messages = normalized[:-keep_last] if len(normalized) > keep_last else []
    recent_messages = normalized[-keep_last:] if keep_last > 0 else []
    digest = _summarize_history_overflow(overflow_messages, previous_digest=previous_digest) if overflow_messages else previous_digest
    return recent_messages, digest


def _compress_history_for_storage(
    history: list[dict[str, Any]] | None,
    *,
    keep_last: int = HISTORY_WINDOW_SIZE,
) -> list[dict[str, Any]]:
    recent_messages, digest = _compress_history_for_context(history, keep_last=keep_last)
    if digest and recent_messages:
        metadata = recent_messages[0].get("metadata")
        normalized_metadata = dict(metadata) if isinstance(metadata, dict) else {}
        normalized_metadata["history_digest"] = digest
        recent_messages[0]["metadata"] = normalized_metadata
    return recent_messages


def _extract_pending_confirmation(history: list[dict[str, Any]] | None) -> dict[str, Any]:
    for item in reversed(history or []):
        if str(item.get("role", "")).strip().lower() != "assistant":
            continue
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            continue
        pending = metadata.get("pending_confirmation")
        if isinstance(pending, dict) and pending:
            return pending
    return {}


def _build_recent_history_summary(
    history: list[dict[str, Any]] | None,
    *,
    max_messages: int = 8,
    max_chars_per_message: int = 240,
) -> str:
    normalized = _normalize_history(history)
    if not normalized:
        return ""

    recent_messages = normalized[-max_messages:]
    lines: list[str] = []
    for item in recent_messages:
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        if len(content) > max_chars_per_message:
            content = content[: max_chars_per_message - 1].rstrip() + "…"
        role_label = "用户" if role == "user" else "助手"
        lines.append(f"{role_label}：{content}")
    return "\n".join(lines)


def _truncate_summary_text(text: str, *, max_chars: int = 500) -> str:
    normalized = str(text or "").strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "…"


def _extract_latest_final_summary(history: list[dict[str, Any]] | None) -> dict[str, Any]:
    for item in reversed(history or []):
        if str(item.get("role", "")).strip().lower() != "assistant":
            continue
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            continue
        final_summary = metadata.get("final_summary")
        if isinstance(final_summary, dict) and final_summary:
            return final_summary
    return {}


def _serialize_previous_task_summary(summary: dict[str, Any]) -> str:
    if not isinstance(summary, dict) or not summary:
        return "无"
    payload = {
        "上轮问题": str(summary.get("rewritten_question", "")).strip()
        or str(summary.get("effective_question", "")).strip(),
        "上轮需求": summary.get("detected_needs", []),
        "上轮背景": str(summary.get("context_summary", "")).strip(),
        "上轮路由": str(summary.get("route", "")).strip(),
    }
    cleaned = {key: value for key, value in payload.items() if value not in ("", [], {}, None)}
    return json.dumps(cleaned, ensure_ascii=False)


def _is_context_dependent_query(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False

    followup_keywords = {
        "??",
        "??",
        "??",
        "??",
        "??",
        "?",
        "??",
        "??",
        "??",
        "?",
        "??",
        "?",
        "??",
        "??",
        "??",
        "??",
        "??",
        "???",
        "???",
        "????",
        "????",
        "???",
        "???",
        "????",
        "??????",
        "?????",
        "????",
        "????",
        "?????",
        "????",
        "??",
        "????",
        "????",
        "???????",
        "????",
        "???",
        "????",
        "??",
        "???",
        "???",
        "???",
        "1km??",
        "1000???",
        "1????",
        "???",
    }
    explicit_followups = {
        "??",
        "???",
        "??",
        "???",
        "???",
        "????",
        "???",
        "??",
        "????",
        "???",
        "???",
        "???1km???",
        "???1000????",
    }
    if normalized in explicit_followups:
        return True
    return any(keyword in normalized for keyword in followup_keywords)



def _is_meta_conversation_query(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False

    meta_keywords = {
        "上一条",
        "上一个问题",
        "上一次",
        "上一轮",
        "前一个问题",
        "前一轮",
        "刚才的问题",
        "你刚刚",
        "你上次",
        "重复上一个",
        "重复之前",
        "聊天记录",
        "历史消息",
        "历史记录",
        "上下文",
        "对话",
        "会话",
        "为什么",
        "怎么回事",
        "为何",
        "why did you",
        "previous question",
        "last question",
        "chat history",
        "conversation history",
        "repeat the previous",
    }
    return any(keyword in normalized for keyword in meta_keywords)


def _has_explicit_continuation_intent(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    continuation_keywords = {
        "继续",
        "接着",
        "顺便",
        "另外",
        "补充",
        "再给我",
        "按刚才",
        "按上一个",
        "基于上一个",
        "基于刚才",
        "在这个行程基础上",
        "沿用上一个",
        "继续刚才",
        "follow up",
        "continue",
        "based on the previous",
    }
    return any(keyword in normalized for keyword in continuation_keywords)


def _looks_like_location_anchor(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False

    explicit_patterns = (
        r"我在[\u4e00-\u9fff0-9a-zA-Z]{2,}",
        r"在[\u4e00-\u9fff0-9a-zA-Z]{2,}",
        r"[\u4e00-\u9fff]{2,}(站|机场|机场站|高铁站|火车站|地铁站|景区|商圈|酒店|广场|园区|大学|公园|区|县|市)",
    )
    if any(re.search(pattern, normalized) for pattern in explicit_patterns):
        return True

    location_keywords = {
        "北京",
        "上海",
        "广州",
        "深圳",
        "杭州",
        "成都",
        "武汉",
        "西安",
        "南京",
        "苏州",
        "重庆",
        "天津",
    }
    return any(keyword in normalized for keyword in location_keywords)


def _is_location_dependent_query(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    location_dependent_keywords = {
        "餐厅",
        "饭店",
        "吃饭",
        "美食",
        "酒店",
        "住宿",
        "住哪",
        "住哪里",
        "附近",
        "周边",
        "步行",
        "公里",
        "米以内",
        "1km",
        "1000米",
        "推荐",
    }
    return any(keyword in normalized for keyword in location_dependent_keywords)


def _needs_location_from_history(question: str, previous_summary: dict[str, Any]) -> bool:
    normalized = str(question or "").strip()
    if not normalized or not isinstance(previous_summary, dict) or not previous_summary:
        return False
    if not _is_location_dependent_query(normalized):
        return False
    if _looks_like_location_anchor(normalized):
        return False

    recommendation_memory = previous_summary.get("recommendation_memory")
    if isinstance(recommendation_memory, dict):
        location_anchor = str(recommendation_memory.get("location_anchor", "")).strip()
        items = recommendation_memory.get("items")
        if location_anchor or (isinstance(items, list) and items):
            return True

    previous_context = str(previous_summary.get("context_summary", "")).strip()
    previous_question = str(previous_summary.get("rewritten_question", "")).strip() or str(
        previous_summary.get("effective_question", "")
    ).strip()
    return _looks_like_location_anchor(previous_context) or _looks_like_location_anchor(previous_question)


def _is_short_ambiguous_recommendation_followup(question: str, previous_summary: dict[str, Any]) -> bool:
    normalized = str(question or "").strip().lower()
    if not normalized or not isinstance(previous_summary, dict):
        return False

    recommendation_memory = previous_summary.get("recommendation_memory")
    if not isinstance(recommendation_memory, dict):
        return False
    items = recommendation_memory.get("items")
    if not isinstance(items, list) or not items:
        return False

    if len(normalized) > 30:
        return False

    anchor_keywords = {
        "餐厅",
        "饭店",
        "酒店",
        "住宿",
        "附近",
        "周边",
        "这几家",
        "那几家",
        "详细",
        "具体",
        "详情",
        "介绍",
        "展开",
        "分别",
        "说说",
        "信息",
        "1km",
        "1 km",
        "1公里",
        "1000米",
        "步行",
        "更近",
    }
    return any(keyword in normalized for keyword in anchor_keywords)


def _is_self_contained_query(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    if _is_context_dependent_query(normalized) or _has_explicit_continuation_intent(normalized):
        return False

    standalone_signals = {
        "我在",
        "从",
        "到",
        "明天",
        "后天",
        "今天",
        "预算",
        "推荐",
        "酒店",
        "餐厅",
        "高铁",
        "火车",
        "飞机",
        "景点",
        "游玩",
        "住",
        "吃",
        "北京",
        "武汉",
        "上海",
        "广州",
        "深圳",
        "station",
        "hotel",
        "restaurant",
        "budget",
        "recommend",
    }
    matched = sum(1 for keyword in standalone_signals if keyword in normalized)
    return matched >= 2 or len(normalized) >= 18


def _extract_inherited_context(previous_summary: dict[str, Any], carry_fields: list[str] | None = None) -> dict[str, Any]:
    if not isinstance(previous_summary, dict) or not previous_summary:
        return {}

    requested = {str(item).strip() for item in (carry_fields or []) if str(item).strip()}
    if not requested:
        requested = {"context_summary", "detected_needs"}

    context: dict[str, Any] = {}
    if "route" in requested:
        route = str(previous_summary.get("route", "")).strip()
        if route:
            context["route"] = route
    if "primary_intent" in requested:
        primary_intent = str(previous_summary.get("primary_intent", "")).strip()
        if primary_intent:
            context["primary_intent"] = primary_intent
    if "context_summary" in requested:
        summary = str(previous_summary.get("context_summary", "")).strip()
        if summary:
            context["context_summary"] = summary
    if "detected_needs" in requested:
        needs = [str(item).strip() for item in previous_summary.get("detected_needs", []) if str(item).strip()]
        if needs:
            context["detected_needs"] = needs
    if "final_answer" in requested:
        final_answer = _truncate_summary_text(str(previous_summary.get("final_answer", "")).strip())
        if final_answer:
            context["final_answer"] = final_answer
    if "recommendation_memory" in requested:
        recommendation_memory = previous_summary.get("recommendation_memory")
        if isinstance(recommendation_memory, dict) and recommendation_memory:
            context["recommendation_memory"] = recommendation_memory
    if "plan_state" in requested:
        plan_state = previous_summary.get("plan_state")
        if isinstance(plan_state, dict) and plan_state:
            context["plan_state"] = plan_state
    if "pending_confirmation" in requested:
        pending = previous_summary.get("pending_confirmation")
        if isinstance(pending, dict) and pending:
            context["pending_confirmation"] = pending
    return context


def _build_context_summary_from_inherited(context: dict[str, Any]) -> str:
    if not isinstance(context, dict) or not context:
        return ""

    parts: list[str] = []
    route = str(context.get("route", "")).strip()
    if route:
        parts.append(f"上轮路由：{route}")
    primary_intent = str(context.get("primary_intent", "")).strip()
    if primary_intent:
        parts.append(f"上轮意图：{primary_intent}")
    summary = str(context.get("context_summary", "")).strip()
    if summary:
        parts.append(f"上轮背景：{summary}")
    needs = context.get("detected_needs", [])
    if isinstance(needs, list) and needs:
        parts.append(f"上轮需求：{json.dumps(needs, ensure_ascii=False)}")
    final_answer = str(context.get("final_answer", "")).strip()
    if final_answer:
        parts.append(f"上轮答复要点：{final_answer}")
    recommendation_memory = context.get("recommendation_memory")
    if isinstance(recommendation_memory, dict):
        items = recommendation_memory.get("items")
        if isinstance(items, list) and items:
            parts.append(f"上轮推荐项数量：{len(items)}")
    plan_state = context.get("plan_state")
    if isinstance(plan_state, dict) and plan_state:
        compact_plan_state = {
            "current_plan_id": plan_state.get("current_plan_id"),
            "plan_draft": plan_state.get("plan_draft", {}),
            "locked_fields": plan_state.get("locked_fields", {}),
            "ready_for_final_confirmation": bool(plan_state.get("ready_for_final_confirmation")),
        }
        compact_plan_state = {key: value for key, value in compact_plan_state.items() if value not in ("", {}, [], None, False)}
        if compact_plan_state:
            parts.append(f"上轮计划状态：{json.dumps(compact_plan_state, ensure_ascii=False)}")
    return "\n".join(parts)


def _extract_topic_tokens(text: str) -> set[str]:
    normalized = str(text or "").lower()
    chinese_tokens = re.findall(r"[\u4e00-\u9fff]{2,}", normalized)
    english_tokens = re.findall(r"[a-z]{3,}", normalized)
    stopwords = {
        "帮我",
        "给我",
        "看看",
        "一下",
        "一个",
        "一份",
        "怎么",
        "如何",
        "关于",
        "相关",
        "推荐",
        "安排",
        "规划",
        "please",
        "help",
        "with",
        "about",
        "need",
        "want",
        "plan",
        "trip",
    }
    return {token for token in chinese_tokens + english_tokens if token not in stopwords}


def _rule_based_inheritance_decision(question: str, previous_summary: dict[str, Any]) -> dict[str, Any] | None:
    normalized = str(question or "").strip()
    if not normalized or not isinstance(previous_summary, dict) or not previous_summary:
        return {"inherit_mode": "none", "carry_fields": [], "reason": "缺少当前问题或上轮摘要"}
    if _is_meta_conversation_query(normalized):
        return {"inherit_mode": "none", "carry_fields": [], "reason": "当前问题是对对话本身的追问"}
    if _needs_location_from_history(normalized, previous_summary):
        return {
            "inherit_mode": "reference_only",
            "carry_fields": ["context_summary", "detected_needs", "final_answer", "recommendation_memory"],
            "reason": "当前问题缺少地点等关键信息，优先参考历史对话中的位置锚点",
        }
    if _is_short_ambiguous_recommendation_followup(normalized, previous_summary):
        return {
            "inherit_mode": "reference_only",
            "carry_fields": ["context_summary", "detected_needs", "final_answer", "recommendation_memory"],
            "reason": "当前问题较短且缺少锚点，优先沿用上轮推荐结果",
        }
    if _is_self_contained_query(normalized):
        return {"inherit_mode": "none", "carry_fields": [], "reason": "当前问题信息完整可独立回答"}
    if _has_explicit_continuation_intent(normalized):
        return {
            "inherit_mode": "task_continue",
            "carry_fields": ["route", "primary_intent", "context_summary", "detected_needs", "final_answer", "recommendation_memory", "plan_state"],
            "reason": "用户明确表示继续上一任务",
        }
    if _is_context_dependent_query(normalized):
        return {
            "inherit_mode": "reference_only",
            "carry_fields": ["context_summary", "detected_needs", "final_answer", "recommendation_memory", "plan_state"],
            "reason": "当前问题依赖上文指代",
        }

    previous_question = str(previous_summary.get("rewritten_question", "")).strip() or str(
        previous_summary.get("effective_question", "")
    ).strip()
    previous_needs = previous_summary.get("detected_needs", [])
    previous_text = "\n".join([previous_question] + [str(item).strip() for item in previous_needs if str(item).strip()])

    current_tokens = _extract_topic_tokens(normalized)
    previous_tokens = _extract_topic_tokens(previous_text)
    if not current_tokens or not previous_tokens:
        return {"inherit_mode": "none", "carry_fields": [], "reason": "主题词不足，无法判定需要继承"}

    overlap = current_tokens & previous_tokens
    overlap_ratio = len(overlap) / max(len(current_tokens), 1)
    if overlap_ratio >= 0.6:
        return {
            "inherit_mode": "reference_only",
            "carry_fields": ["context_summary", "detected_needs", "final_answer", "recommendation_memory"],
            "reason": "当前问题与上轮主题高度重合",
        }
    if len(normalized) <= 10 and overlap_ratio >= 0.34:
        return {
            "inherit_mode": "reference_only",
            "carry_fields": ["context_summary", "detected_needs", "final_answer", "recommendation_memory"],
            "reason": "当前问题较短且与上轮主题有重合",
        }
    return None


def _llm_inheritance_decision(question: str, previous_summary: dict[str, Any]) -> dict[str, Any]:
    normalized = str(question or "").strip()
    if not normalized or not isinstance(previous_summary, dict) or not previous_summary:
        return {"inherit_mode": "none", "carry_fields": [], "reason": "缺少当前问题或上轮摘要"}
    if _is_meta_conversation_query(normalized):
        return {"inherit_mode": "none", "carry_fields": [], "reason": "当前问题是对对话本身的追问"}
    if _is_self_contained_query(normalized):
        return {"inherit_mode": "none", "carry_fields": [], "reason": "当前问题信息完整可独立回答"}

    previous_question = str(previous_summary.get("rewritten_question", "")).strip() or str(
        previous_summary.get("effective_question", "")
    ).strip()
    previous_needs = [str(item).strip() for item in previous_summary.get("detected_needs", []) if str(item).strip()]
    previous_context = str(previous_summary.get("context_summary", "")).strip()
    if not previous_question and not previous_needs and not previous_context:
        return {"inherit_mode": "none", "carry_fields": [], "reason": "上轮摘要为空"}

    try:
        parsed = _safe_json_llm(
            system_prompt=(
                "你是上下文继承判定助手。"
                "请判断当前用户问题是否应该继承上一轮任务摘要。"
                "只返回 JSON，且必须包含三个字段：inherit_mode、carry_fields、reason。"
                "inherit_mode 只能是 none、reference_only、task_continue 之一。"
                "carry_fields 只能从 route、primary_intent、context_summary、detected_needs、final_answer、recommendation_memory、plan_state、pending_confirmation 中选择。"
                "如果当前问题本身信息完整，可独立回答，则使用 none。"
                "如果只是需要借用少量上文来消解指代，则使用 reference_only。"
                "如果用户明确是在继续上一轮任务，则使用 task_continue。"
            ),
            user_prompt=(
                f"当前问题：{normalized}\n"
                f"上轮改写后问题：{previous_question}\n"
                f"上轮识别需求：{json.dumps(previous_needs, ensure_ascii=False)}\n"
                f"上轮上下文摘要：{previous_context}"
            ),
            history=None,
        )
    except Exception:
        return {"inherit_mode": "none", "carry_fields": [], "reason": "继承分类器调用失败"}

    if not isinstance(parsed, dict):
        return {"inherit_mode": "none", "carry_fields": [], "reason": "继承分类器返回格式异常"}

    inherit_mode = str(parsed.get("inherit_mode", "none")).strip().lower()
    if inherit_mode not in {"none", "reference_only", "task_continue"}:
        inherit_mode = "none"
    carry_fields = [
        str(item).strip()
        for item in parsed.get("carry_fields", [])
        if str(item).strip() in {"route", "primary_intent", "context_summary", "detected_needs", "final_answer", "recommendation_memory", "plan_state", "pending_confirmation"}
    ]
    if inherit_mode == "none":
        carry_fields = []
    elif not carry_fields:
        carry_fields = ["context_summary", "detected_needs"]
    return {
        "inherit_mode": inherit_mode,
        "carry_fields": carry_fields,
        "reason": str(parsed.get("reason", "")).strip() or "由模型判定继承方式",
    }


def _decide_inheritance(question: str, previous_summary: dict[str, Any]) -> dict[str, Any]:
    rule_decision = _rule_based_inheritance_decision(question, previous_summary)
    if rule_decision is not None:
        return rule_decision
    return _llm_inheritance_decision(question, previous_summary)


def _is_confirmation_reply(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    return bool(normalized) and any(keyword in normalized for keyword in _CONFIRM_REPLY_KEYWORDS)


def _normalize_confirmation_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip().lower())


def _build_confirmation_signature(*, route: str, rewritten_question: str, detected_needs: list[str] | None = None) -> str:
    normalized_needs = [
        _normalize_confirmation_text(item)
        for item in (detected_needs or [])
        if _normalize_confirmation_text(item)
    ]
    payload = {
        "route": _normalize_confirmation_text(route),
        "rewritten_question": _normalize_confirmation_text(rewritten_question),
        "detected_needs": normalized_needs,
    }
    if not payload["rewritten_question"] and not normalized_needs:
        return ""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _extract_last_confirmed_signature(history: list[dict[str, Any]] | None) -> str:
    for item in reversed(history or []):
        if str(item.get("role", "")).strip().lower() != "assistant":
            continue
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            continue
        final_summary = metadata.get("final_summary")
        if not isinstance(final_summary, dict):
            continue
        signature = str(final_summary.get("confirmation_signature", "")).strip()
        if signature:
            return signature
    return ""


def _resolve_effective_question(state: ChatGraphState) -> tuple[str, bool, dict[str, Any], dict[str, Any], dict[str, Any]]:
    question = str(state.get("question", "")).strip()
    history = state.get("raw_history", state.get("history"))
    pending_confirmation = _extract_pending_confirmation(history)
    previous_task_summary = _extract_latest_final_summary(history)
    if pending_confirmation and _is_confirmation_reply(question):
        original_question = str(pending_confirmation.get("original_question", "")).strip()
        if original_question:
            return (
                original_question,
                True,
                pending_confirmation,
                previous_task_summary,
                {
                    "inherit_mode": "task_continue",
                    "carry_fields": ["route", "primary_intent", "context_summary", "detected_needs", "final_answer", "recommendation_memory", "plan_state"],
                    "reason": "当前输入是确认回复",
                },
            )
    if previous_task_summary:
        return question, False, pending_confirmation, previous_task_summary, _decide_inheritance(question, previous_task_summary)
    return question, False, pending_confirmation, {}, {"inherit_mode": "none", "carry_fields": [], "reason": "没有上轮摘要"}


def _last_user_query(state: ChatGraphState) -> str:
    rewritten = str(state.get("rewritten_question", "")).strip()
    if rewritten:
        return rewritten
    effective = str(state.get("effective_question", "")).strip()
    if effective:
        return effective
    return str(state.get("question", "")).strip()


def _contains_any(text: str, keywords: set[str] | list[str] | tuple[str, ...]) -> bool:
    return any(str(keyword).strip().lower() in text for keyword in keywords if str(keyword).strip())


def _is_lodging_query(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    lodging_keywords = {"住宿", "住哪里", "酒店", "宾馆", "民宿", "旅店", "客栈", "青旅", "旅馆"}
    return bool(normalized) and any(keyword.lower() in normalized for keyword in lodging_keywords)


def _is_scenic_query(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    scenic_keywords = {"景点", "景区", "景色", "游玩", "打卡", "公园", "博物馆", "古镇", "海边", "寺庙"}
    return bool(normalized) and any(keyword.lower() in normalized for keyword in scenic_keywords)


def _is_itinerary_request(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    itinerary_keywords = {
        "路线",
        "线路",
        "行程",
        "攻略",
        "规划",
        "安排",
        "怎么安排",
        "游玩顺序",
        "一日游路线",
        "两天一夜行程",
        "itinerary",
        "route",
        "plan",
    }
    return bool(normalized) and any(keyword.lower() in normalized for keyword in itinerary_keywords)


def _is_recommendation_request(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    recommendation_keywords = {
        "推荐",
        "推荐下",
        "有什么推荐",
        "哪些值得去",
        "值得去",
        "必去",
        "必玩",
        "哪里好玩",
        "哪个号",
        "适合",
        "rank",
        "recommend",
    }
    return bool(normalized) and any(keyword.lower() in normalized for keyword in recommendation_keywords)


def _is_simple_scenic_recommendation(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    return bool(normalized) and _is_scenic_query(normalized) and _is_recommendation_request(normalized) and not _is_itinerary_request(normalized)


def _is_rule_knowledge_query(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized or _is_itinerary_request(normalized):
        return False

    has_rule_keyword = _contains_any(normalized, _RAG_RULE_KEYWORDS)
    has_rag_topic = _contains_any(normalized, _RAG_KEYWORDS) or _contains_any(
        normalized,
        {"火车票", "高铁票", "车票", "铁路", "车站", "乘车", "检票", "12306", "退票", "改签", "候补", "购票", "出行规则"},
    )
    has_explicit_lookup = _contains_any(
        normalized,
        {"余票", "查票", "抢票", "订票", "买票", "下单", "车次查询", "票价查询", "有没有票"},
    )
    if has_rule_keyword and has_rag_topic and not has_explicit_lookup:
        return True
    if has_rag_topic and _contains_any(normalized, {"使用规则", "退票规则", "改签规则", "候补规则", "乘车规定"}):
        return True
    return False


def _extract_json(content: str) -> dict[str, Any]:
    text = _strip_think_tags(content).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in response")
    return json.loads(text[start : end + 1])


def _safe_json_llm(*, system_prompt: str, user_prompt: str, history: list[dict[str, str]] | None) -> dict[str, Any]:
    llm = _build_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", user_prompt),
        ]
    )
    response = llm.invoke(prompt.format_messages(chat_history=_normalize_history(history)))
    content = str(getattr(response, "content", response))
    return _extract_json(content)


def _combined_route_text(state: ChatGraphState) -> str:
    parts = [
        str(state.get("question", "")).strip(),
        str(state.get("effective_question", "")).strip(),
        str(state.get("rewritten_question", "")).strip(),
    ]
    return "\n".join(part for part in parts if part).lower()


def _extract_latest_plan_state_from_history(history: list[dict[str, Any]] | None) -> dict[str, Any]:
    for item in reversed(history or []):
        if str(item.get("role", "")).strip().lower() != "assistant":
            continue
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            continue
        final_summary = metadata.get("final_summary")
        if not isinstance(final_summary, dict):
            continue
        plan_state = final_summary.get("plan_state")
        if isinstance(plan_state, dict) and plan_state:
            return {
                "current_plan_id": plan_state.get("current_plan_id"),
                "plan_draft": dict(plan_state.get("plan_draft", {}) or {}),
                "locked_fields": dict(plan_state.get("locked_fields", {}) or {}),
                "candidate_options": list(plan_state.get("candidate_options", []) or []),
                "image_items": list(plan_state.get("image_items", []) or []),
                "ready_for_final_confirmation": bool(plan_state.get("ready_for_final_confirmation")),
                "final_confirmation_payload": dict(plan_state.get("final_confirmation_payload", {}) or {}),
            }
    return {
        "current_plan_id": None,
        "plan_draft": {},
        "locked_fields": {},
        "candidate_options": [],
        "image_items": [],
        "ready_for_final_confirmation": False,
        "final_confirmation_payload": {},
    }


def _is_travel_plan_query(state: ChatGraphState) -> bool:
    combined = "\n".join(
        [
            str(state.get("question", "")).strip(),
            str(state.get("effective_question", "")).strip(),
            str(state.get("rewritten_question", "")).strip(),
        ]
    ).lower()
    if _is_simple_scenic_recommendation(combined):
        return False
    if any(keyword.lower() in combined for keyword in _TRAVEL_PLAN_KEYWORDS) and _is_itinerary_request(combined):
        return True
    prior_routes = {str(item).strip().lower() for item in state.get("prior_routes", [])}
    if "roadmap" in prior_routes:
        return True
    if "ticket" in prior_routes and not _is_simple_scenic_recommendation(combined):
        return True
    previous = _extract_latest_plan_state_from_history(state.get("raw_history", state.get("history")))
    return bool(previous.get("plan_draft") or previous.get("locked_fields") or previous.get("current_plan_id"))


def _build_plan_state_output(state: ChatGraphState) -> dict[str, Any]:
    return {
        "current_plan_id": state.get("current_plan_id"),
        "plan_draft": dict(state.get("plan_draft", {}) or {}),
        "locked_fields": dict(state.get("locked_fields", {}) or {}),
        "candidate_options": list(state.get("candidate_options", []) or []),
        "image_items": list(state.get("image_items", []) or []),
        "ready_for_final_confirmation": bool(state.get("ready_for_final_confirmation")),
        "final_confirmation_payload": dict(state.get("final_confirmation_payload", {}) or {}),
    }


def _extract_image_urls(text: str) -> list[str]:
    if not text:
        return []

    urls: list[str] = []
    markdown_matches = re.findall(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", text, flags=re.IGNORECASE)
    direct_matches = re.findall(r"https?://[^\s<>\])，。；;,]+", text, flags=re.IGNORECASE)
    image_field_matches = re.findall(r"图片[:：]\s*(.+)", text, flags=re.IGNORECASE)
    image_suffixes = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")

    candidates: list[str] = []
    candidates.extend(markdown_matches)
    candidates.extend(direct_matches)

    for field in image_field_matches:
        for part in re.split(r"[；;、,\s]+", field.strip()):
            if part.startswith("http://") or part.startswith("https://"):
                candidates.append(part)

    for url in candidates:
        normalized = url.rstrip(").,;]），。；")
        lowered = normalized.lower()
        if lowered.endswith(image_suffixes) or any(
            token in lowered for token in ("image", "img", "photo", "picture", "staticmap", "snapshot")
        ):
            if normalized not in urls:
                urls.append(normalized)
    return urls


def _build_image_items(text: str) -> list[dict[str, str]]:
    if not text:
        return []

    image_urls = _extract_image_urls(text)
    if not image_urls:
        return []

    lines = [line.strip() for line in text.splitlines()]
    items: list[dict[str, str]] = []
    generic_prefixes = ("图片", "推荐理由", "理由", "位置", "地址", "交通", "距离", "价格", "人均", "营业时间", "建议", "适合")

    def normalize_candidate(line: str) -> str:
        cleaned = re.sub(r"^[\-*\d\.\s]+", "", line).strip()
        if cleaned.startswith("**") and cleaned.endswith("**") and len(cleaned) > 4:
            cleaned = cleaned[2:-2].strip()
        return cleaned.strip().strip(":").strip("?").strip()

    def looks_like_name(line: str) -> bool:
        candidate = normalize_candidate(line)
        if not candidate or any(candidate.startswith(prefix) for prefix in generic_prefixes) or "http" in candidate:
            return False
        return len(candidate) <= 40

    def infer_anchor_text(url: str) -> str:
        for index, line in enumerate(lines):
            if url not in line:
                continue
            best_fallback = ""
            for offset in range(index - 1, max(-1, index - 8), -1):
                candidate = normalize_candidate(lines[offset])
                if not candidate or candidate.startswith("图片") or "http" in candidate:
                    continue
                if not best_fallback:
                    best_fallback = candidate[:80]
                if looks_like_name(candidate):
                    return candidate[:80]
            return best_fallback
        return ""

    for index, url in enumerate(image_urls):
        anchor_text = infer_anchor_text(url)
        items.append(
            {
                "image_url": url,
                "title": anchor_text or f"图片 {index + 1}",
                "category": "",
                "anchor_text": anchor_text,
            }
        )
    return items


def _inline_image_markdown(text: str, max_images_per_block: int = 1) -> str:
    if not text:
        return text

    def repl(match: re.Match[str]) -> str:
        raw = match.group(1).strip()
        if not raw or raw == "暂无":
            return "图片：暂无"
        urls = [part.strip() for part in re.split(r"[；;、,\s]+", raw) if part.strip().startswith(("http://", "https://"))]
        if not urls:
            return f"图片：{raw}"
        return "图片：\n" + "\n".join(f"![]({url})" for url in urls[:max_images_per_block])

    return re.sub(r"图片[:：]\s*(.+)", repl, text, flags=re.IGNORECASE)


def _inline_loose_image_urls(text: str, max_total_images: int = 6) -> str:
    if not text:
        return text

    protected_markdown_urls = {
        match.rstrip(").,;]），。；")
        for match in re.findall(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", text, flags=re.IGNORECASE)
    }
    image_suffixes = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")
    replaced_count = 0
    rendered_anchor_keys: set[str] = set()
    lines = text.splitlines()

    def normalize_anchor_key(value: str) -> str:
        normalized = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", str(value or ""))
        normalized = re.sub(r"https?://\S+", "", normalized)
        normalized = re.sub(r"^[\-\*\d\.\)\(、\s]+", "", normalized)
        normalized = re.sub(r"[\s:：,，。；;!！?？\[\]\(\)（）`*_#]+", "", normalized)
        return normalized.strip().lower()

    def infer_anchor_key(index: int) -> str:
        for offset in range(index - 1, -1, -1):
            candidate = lines[offset].strip()
            if not candidate or candidate.startswith("![](") or candidate.startswith("图片："):
                continue
            if "http://" in candidate or "https://" in candidate:
                continue
            normalized = normalize_anchor_key(candidate)
            if normalized:
                return normalized
        return f"line:{index}"

    rendered_lines: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            rendered_lines.append(line)
            continue
        if stripped.startswith("![]("):
            rendered_lines.append(line)
            continue

        matches = list(re.finditer(r"https?://[^\s<>\])，。；;,]+", line, flags=re.IGNORECASE))
        if not matches:
            rendered_lines.append(line)
            continue

        anchor_key = infer_anchor_key(index)
        line_output = line
        appended_image = ""
        kept_any_image = False

        for match in reversed(matches):
            raw = match.group(0)
            url = raw.rstrip(").,;]），。；")
            lowered = url.lower()
            is_image_url = lowered.endswith(image_suffixes) or any(
                token in lowered for token in ("image", "img", "photo", "picture", "staticmap", "snapshot")
            )
            if not is_image_url or url in protected_markdown_urls:
                continue

            line_output = line_output[: match.start()] + line_output[match.end() :]
            if kept_any_image or replaced_count >= max_total_images or anchor_key in rendered_anchor_keys:
                continue

            appended_image = f"\n![]({url})\n"
            kept_any_image = True
            replaced_count += 1
            rendered_anchor_keys.add(anchor_key)

        rendered_lines.append(line_output.rstrip())
        if appended_image:
            rendered_lines.append(appended_image.rstrip("\n"))
    return "\n".join(rendered_lines)


def _render_images_in_answer(text: str) -> str:
    if not text:
        return text
    return _inline_loose_image_urls(_inline_image_markdown(text))
