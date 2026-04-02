from __future__ import annotations

import re

from .shared import (
    _HOTEL_OBJECT_KEYWORDS,
    _SPECIFIC_TICKET_DETAIL_KEYWORDS,
    _SPECIFIC_TICKET_OBJECT_KEYWORDS,
    ChatGraphState,
    _build_confirmation_signature,
    _emit_node_complete,
    _emit_node_start,
    _extract_last_confirmed_signature,
    _last_user_query,
)


_EXPLICIT_BOOKING_KEYWORDS = {
    "帮我订",
    "帮我预订",
    "帮我预定",
    "帮我订购",
    "帮我下单",
    "帮我预约",
    "直接订",
    "直接预订",
    "直接预定",
    "确认预订",
    "确认预定",
    "去订",
    "下单吧",
    "现在订",
    "立即预订",
    "book it",
    "book this",
    "place the order",
    "confirm booking",
}


def _has_explicit_booking_intent(query: str) -> bool:
    normalized = str(query or "").strip().lower()
    return bool(normalized) and any(keyword.lower() in normalized for keyword in _EXPLICIT_BOOKING_KEYWORDS)


def _needs_confirmation(state: ChatGraphState) -> bool:
    if bool(state.get("confirmed")):
        return False

    query = _last_user_query(state).lower()
    if not query or not _has_explicit_booking_intent(query):
        return False

    has_hotel_object = any(keyword.lower() in query for keyword in _HOTEL_OBJECT_KEYWORDS)
    has_hotel_detail = bool(
        re.search(r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[:：]\d{0,2}|住\d+\s*晚|\d+\s*(晚|人|间)", query)
    )
    if has_hotel_object:
        return has_hotel_detail

    has_ticket_object = any(keyword.lower() in query for keyword in _SPECIFIC_TICKET_OBJECT_KEYWORDS)
    if not has_ticket_object:
        return False

    has_ticket_detail_keyword = any(keyword.lower() in query for keyword in _SPECIFIC_TICKET_DETAIL_KEYWORDS)
    has_ticket_datetime = bool(re.search(r"\d{1,2}\s*[:：]\s*\d{0,2}|\d{4}-\d{1,2}-\d{1,2}", query))
    has_train_or_flight_no = bool(re.search(r"\b[a-z]{0,2}\d{2,4}\b", query))
    return has_ticket_detail_keyword and (has_ticket_datetime or has_train_or_flight_no)


def confirmation_gate(state: ChatGraphState) -> dict[str, object]:
    _emit_node_start("confirmation_gate", "正在检查是否需要确认")
    if bool(state.get("confirmed")) or not _needs_confirmation(state):
        result = {
            "requires_confirmation": False,
            "status": "completed",
            "pending_confirmation": {},
        }
        _emit_node_complete("confirmation_gate", "无需确认", status="completed")
        return result

    rewritten_question = _last_user_query(state)
    current_signature = _build_confirmation_signature(
        route=str(state.get("route", "other")).strip(),
        rewritten_question=rewritten_question,
        detected_needs=state.get("detected_needs", []),
    )
    last_confirmed_signature = _extract_last_confirmed_signature(state.get("raw_history", state.get("history")))
    if current_signature and current_signature == last_confirmed_signature:
        result = {
            "requires_confirmation": False,
            "status": "completed",
            "pending_confirmation": {},
        }
        _emit_node_complete("confirmation_gate", "本轮已确认过，直接继续", status="completed")
        return result

    pending_confirmation = {
        "original_question": str(state.get("effective_question", state.get("question", ""))).strip(),
        "rewritten_question": rewritten_question,
        "route": str(state.get("route", "other")).strip(),
        "detected_needs": state.get("detected_needs", []),
        "confirmation_signature": current_signature,
    }
    answer = (
        f"我理解你的意思是：\n{rewritten_question}\n\n"
        "这一步会触发实际预订或下单操作。\n"
        "如果你确认让我继续，请直接回复“确认”或说明要调整的内容。"
    )
    result = {
        "requires_confirmation": True,
        "status": "needs_confirmation",
        "pending_confirmation": pending_confirmation,
        "answer": answer,
        "answer_source": "confirmation_gate",
    }
    _emit_node_complete("confirmation_gate", "需要用户确认", status="needs_confirmation")
    return result


def after_confirmation_gate(state: ChatGraphState) -> str:
    if bool(state.get("requires_confirmation")):
        return "await_confirmation"
    return "execute_tasks"


def await_confirmation(state: ChatGraphState) -> dict[str, object]:
    _emit_node_start("await_confirmation", "等待用户确认")
    result = {
        "answer": str(state.get("answer", "")).strip(),
        "answer_source": str(state.get("answer_source", "confirmation_gate")).strip() or "confirmation_gate",
        "status": "needs_confirmation",
        "verification": {
            "is_complete": False,
            "covered_needs": [],
            "missing_needs": state.get("detected_needs", []),
            "unsupported_needs": [],
            "answer_source": "confirmation_gate",
        },
    }
    _emit_node_complete("await_confirmation", "已返回确认提示", status="needs_confirmation")
    return result
