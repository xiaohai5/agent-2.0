from __future__ import annotations

import json

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from .shared import (
    FIELD_LABELS,
    ChatGraphState,
    _build_confirmation_signature,
    _build_image_items,
    _build_plan_state_output,
    _coerce_stream_chunk_text,
    _emit_node_complete,
    _emit_node_error,
    _emit_node_start,
    _emit_stream_event,
    _extract_image_urls,
    _is_travel_plan_query,
    _last_user_query,
    _normalize_history,
    _render_images_in_answer,
    _safe_json_llm,
    _strip_think_tags,
)


def _compose_multitask_answer(state: ChatGraphState) -> str:
    task_outputs = state.get("task_outputs", {}) or {}
    if not isinstance(task_outputs, dict) or not task_outputs:
        return str(state.get("draft_answer", state.get("answer", ""))).strip()

    non_empty_routes = [
        route
        for route, payload in task_outputs.items()
        if str(payload.get("draft_answer", payload.get("answer", ""))).strip()
    ]
    if len(non_empty_routes) <= 1:
        route = non_empty_routes[0] if non_empty_routes else next(iter(task_outputs), "")
        payload = task_outputs.get(route, {})
        return str(
            payload.get(
                "draft_answer",
                payload.get("answer", state.get("draft_answer", state.get("answer", ""))),
            )
        ).strip()

    title_map = {
        "roadmap": "行程规划",
        "ticket": "票务查询",
        "rag": "知识检索",
        "other": "通用回复",
    }
    sections: list[str] = []
    for route in non_empty_routes:
        body = str(
            task_outputs.get(route, {}).get(
                "draft_answer",
                task_outputs.get(route, {}).get("answer", ""),
            )
        ).strip()
        sections.append(f"{title_map.get(route, route)}\n{body}")
    return "\n\n".join(sections).strip()


def compose_answer(state: ChatGraphState) -> dict[str, object]:
    _emit_node_start("compose_answer", "正在整合各路任务结果")
    try:
        draft_answer = _compose_multitask_answer(state)
    except Exception:
        draft_answer = str(state.get("draft_answer", state.get("answer", ""))).strip()

    task_outputs = state.get("task_outputs", {}) or {}
    source = str(state.get("answer_source", "")).strip() or "multi_task"
    if isinstance(task_outputs, dict) and len(task_outputs) > 1:
        source = "multi_task"

    result = {
        "draft_answer": _render_images_in_answer(draft_answer),
        "answer_source": source,
    }
    _emit_node_complete("compose_answer", "结果整合完成", answer_source=source)
    return result


def after_execute_tasks(state: ChatGraphState) -> str:
    routes = [str(item).strip().lower() for item in state.get("subtask_routes", []) if str(item).strip()]
    if routes == ["other"]:
        return "other_route_rewriter"
    return "compose_answer"


def _extract_recommendation_memory(state: ChatGraphState, final_answer: str) -> dict[str, object]:
    answer_text = str(final_answer or "").strip()
    if not answer_text:
        return {}

    query_text = "\n".join(
        [
            str(state.get("question", "")).strip(),
            str(state.get("effective_question", "")).strip(),
            str(state.get("rewritten_question", "")).strip(),
        ]
    ).lower()
    trigger_keywords = {"推荐", "餐厅", "酒店", "民宿", "住宿", "饭店", "restaurant", "hotel", "recommend"}
    if not any(keyword in query_text for keyword in trigger_keywords):
        return {}

    try:
        parsed = _safe_json_llm(
            system_prompt=(
                "你是推荐结果结构化提取助手。"
                "请从给定问题与回答中提取推荐项，返回 JSON。"
                "只返回两个字段：location_anchor 和 items。"
                "items 必须是数组，每项允许包含：name、type、distance_m、price_note、address_note、reason。"
                "type 只能是 restaurant、hotel、other。"
                "distance_m 必须是数字；无法判断时填 null。"
                "如果回答里没有明确推荐项，就返回空数组。"
            ),
            user_prompt=(
                f"问题：{_last_user_query(state)}\n"
                f"回答：{answer_text}"
            ),
            history=None,
        )
    except Exception:
        return {}

    if not isinstance(parsed, dict):
        return {}

    items_payload = parsed.get("items", [])
    if not isinstance(items_payload, list):
        return {}

    items: list[dict[str, object]] = []
    for item in items_payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        item_type = str(item.get("type", "other")).strip().lower()
        if item_type not in {"restaurant", "hotel", "other"}:
            item_type = "other"
        distance_value = item.get("distance_m")
        if isinstance(distance_value, (int, float)):
            distance_m: int | None = int(distance_value)
        else:
            try:
                distance_m = int(str(distance_value).strip()) if str(distance_value).strip() else None
            except Exception:
                distance_m = None
        items.append(
            {
                "name": name,
                "type": item_type,
                "distance_m": distance_m,
                "price_note": str(item.get("price_note", "")).strip(),
                "address_note": str(item.get("address_note", "")).strip(),
                "reason": str(item.get("reason", "")).strip(),
            }
        )

    if not items:
        return {}

    return {
        "location_anchor": str(parsed.get("location_anchor", "")).strip(),
        "items": items,
    }


def _build_final_summary_payload(state: ChatGraphState, final_answer: str) -> dict[str, object]:
    rewritten_question = _last_user_query(state)
    is_confirmed = bool(state.get("confirmed"))
    confirmation_signature = ""
    recommendation_memory = _extract_recommendation_memory(state, final_answer)
    if is_confirmed:
        confirmation_signature = _build_confirmation_signature(
            route=str(state.get("route", "")).strip(),
            rewritten_question=rewritten_question,
            detected_needs=state.get("detected_needs", []),
        )
    return {
        "original_question": str(state.get("question", "")).strip(),
        "effective_question": str(state.get("effective_question", "")).strip(),
        "rewritten_question": rewritten_question,
        "inherit_mode": str(state.get("inherit_mode", "none")).strip() or "none",
        "carry_fields": state.get("carry_fields", []),
        "inherit_reason": str(state.get("inherit_reason", "")).strip(),
        "inherited_context": state.get("inherited_context", {}),
        "prior_routes": state.get("prior_routes", []),
        "detected_needs": state.get("detected_needs", []),
        "context_summary": str(state.get("context_summary", "")).strip(),
        "route": str(state.get("route", "")).strip(),
        "primary_intent": str(state.get("primary_intent", "")).strip(),
        "subtask_routes": state.get("subtask_routes", []),
        "task_outputs": state.get("task_outputs", {}),
        "plan_state": _build_plan_state_output(state) if _is_travel_plan_query(state) else {},
        "status": str(state.get("status", "completed")).strip() or "completed",
        "pending_confirmation": state.get("pending_confirmation", {}),
        "confirmed": is_confirmed,
        "confirmation_signature": confirmation_signature,
        "answer_source": str(state.get("answer_source", "")).strip(),
        "verification": state.get("verification", {}),
        "recommendation_memory": recommendation_memory,
        "recent_history_summary": str(state.get("recent_history_summary", "")).strip(),
        "other_memory_summary": str(state.get("other_memory_summary", "")).strip(),
        "image_urls": _extract_image_urls(final_answer),
        "image_items": list(state.get("image_items", []) or []) or _build_image_items(final_answer),
        "final_answer": final_answer,
    }


def verify_answer(state: ChatGraphState) -> dict[str, object]:
    _emit_node_start("verify_answer", "正在检查答案是否覆盖用户需求")
    if str(state.get("status", "completed")).strip().lower() == "needs_confirmation":
        result = {
            "verification": {
                "is_complete": False,
                "covered_needs": [],
                "missing_needs": state.get("detected_needs", []),
                "unsupported_needs": [],
                "answer_source": "confirmation_gate",
            }
        }
        _emit_node_complete("verify_answer", "确认场景跳过完整性校验", is_complete=False)
        return result

    draft_answer = str(state.get("draft_answer", state.get("answer", ""))).strip()
    detected_needs = state.get("detected_needs", [])
    fallback = {
        "is_complete": bool(draft_answer),
        "covered_needs": detected_needs if draft_answer else [],
        "missing_needs": [] if draft_answer else detected_needs,
        "unsupported_needs": [],
        "answer_source": str(state.get("answer_source", "")).strip(),
    }

    try:
        parsed = _safe_json_llm(
            system_prompt=(
                "请检查答案是否覆盖了用户需求。"
                "返回 JSON，字段包括 is_complete、covered_needs、missing_needs、unsupported_needs、answer_source。"
            ),
            user_prompt=(
                f"原始问题：{str(state.get('question', '')).strip()}\n"
                f"重写问题：{_last_user_query(state)}\n"
                f"历史路由：{json.dumps(state.get('prior_routes', []), ensure_ascii=False)}\n"
                f"识别需求：{json.dumps(detected_needs, ensure_ascii=False)}\n"
                f"答案来源：{str(state.get('answer_source', '')).strip()}\n"
                f"草稿答案：{draft_answer}"
            ),
            history=state.get("history"),
        )
    except Exception:
        parsed = fallback

    verification = {
        "is_complete": bool(parsed.get("is_complete", fallback["is_complete"]))
        if isinstance(parsed, dict)
        else fallback["is_complete"],
        "covered_needs": [
            str(item).strip()
            for item in (
                parsed.get("covered_needs", fallback["covered_needs"])
                if isinstance(parsed, dict)
                else fallback["covered_needs"]
            )
            if str(item).strip()
        ],
        "missing_needs": [
            str(item).strip()
            for item in (
                parsed.get("missing_needs", fallback["missing_needs"])
                if isinstance(parsed, dict)
                else fallback["missing_needs"]
            )
            if str(item).strip()
        ],
        "unsupported_needs": [
            str(item).strip()
            for item in (
                parsed.get("unsupported_needs", fallback["unsupported_needs"])
                if isinstance(parsed, dict)
                else fallback["unsupported_needs"]
            )
            if str(item).strip()
        ],
        "answer_source": str(parsed.get("answer_source", fallback["answer_source"]))
        if isinstance(parsed, dict)
        else fallback["answer_source"],
    }
    _emit_node_complete("verify_answer", "答案校验完成", is_complete=verification["is_complete"])
    return {"verification": verification}


def _build_customer_friendly_confirmation_text(final_payload: dict[str, object]) -> str:
    locked_items = final_payload.get("locked_items", {}) if isinstance(final_payload, dict) else {}
    label_map = {
        "origin": "出发地",
        "destination": "目的地",
        "departure_date": "出发日期",
        "return_date": "返回日期",
        "travelers": "出行人数",
        "budget": "预算",
    }
    lines = ["我已经整理好了当前确认信息，请你核对："]
    for field_name in ("origin", "destination", "departure_date", "return_date", "travelers", "budget"):
        value = final_payload.get(field_name)
        if value not in (None, "", [], {}):
            lines.append(f"- {label_map.get(field_name, field_name)}：{value}")
    if isinstance(locked_items, dict) and locked_items:
        lines.append("- 已锁定信息：")
        for key, value in locked_items.items():
            lines.append(f"  - {FIELD_LABELS.get(str(key), str(key))}：{value}")
    summary = str(final_payload.get("plan_summary", "")).strip()
    if summary:
        lines.append(f"- 当前计划摘要：{summary}")
    lines.append("如果内容无误，请直接回复“确认”；如果要调整，请告诉我需要修改的部分。")
    return "\n".join(lines)


# `other` 路由专用收口器：用于整理开放问答、历史追问或泛化回复，
# 只负责自然表达，不负责产出固定业务计划结构。
async def other_route_rewriter(state: ChatGraphState) -> dict[str, object]:
    _emit_node_start("other_route_rewriter", "正在整理通用回复")
    raw_answer = str(state.get("draft_answer", state.get("answer", ""))).strip()
    if not raw_answer:
        _emit_node_complete("other_route_rewriter", "没有可整理的内容")
        final_answer = raw_answer
    else:
        other_history = state.get("other_history") or state.get("history")
        other_memory_summary = str(state.get("other_memory_summary", "")).strip() or str(
            state.get("recent_history_summary", "")
        ).strip()
        llm = ChatOpenAI(model="lora", base_url="http://localhost:1522/v1", api_key="123456")
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是中文智能客服助手，输出可爱搞怪但专业、信息完整、不遗漏关键事实、带有表情的最终客服回复。"
                    "不要强行套用固定格式，也不要自动扩写成完整计划。"
                    "根据问题来判断用户是否在追问历史信息，如果用户在追问历史信息，请根据历史信息给出回复。",
                ),
                MessagesPlaceholder(variable_name="chat_history"),
                (
                    "user",
                    "当前问题：{question}\n"
                    "识别需求：{needs}\n"
                    "上下文摘要：{context_summary}\n"
                    "最近几轮对话摘要：{recent_history_summary}\n"
                    "草稿答案：\n{raw_answer}\n\n"
                    "请将它改写成一段清晰自然的最终回复。",
                ),
            ]
        )
        messages = prompt.format_messages(
            chat_history=_normalize_history(other_history),
            question=_last_user_query(state),
            needs=json.dumps(state.get("detected_needs", []), ensure_ascii=False),
            context_summary=str(state.get("context_summary", "")).strip() or "无",
            recent_history_summary=other_memory_summary or "无",
            raw_answer=raw_answer,
        )
        streamed_parts: list[str] = []
        try:
            async for chunk in llm.astream(messages):
                piece = _coerce_stream_chunk_text(getattr(chunk, "content", chunk))
                if not piece:
                    continue
                streamed_parts.append(piece)
                _emit_stream_event("delta", node="other_route_rewriter", content=piece)
        except Exception as exc:
            _emit_node_error("other_route_rewriter", str(exc).strip() or exc.__class__.__name__)
            raise
        final_answer = _strip_think_tags("".join(streamed_parts)).strip() or raw_answer
        _emit_node_complete("other_route_rewriter", "通用回复整理完成")

    return {
        "answer": final_answer,
        "answer_source": str(state.get("answer_source", "")).strip() or "general_llm",
        "final_summary": _build_final_summary_payload(state, final_answer),
    }


# 业务路由专用收口器：用于在结果整合和校验之后，
# 生成面向用户的最终客服化表达。
async def customer_service_rewriter(state: ChatGraphState) -> dict[str, object]:
    _emit_node_start("customer_service_rewriter", "正在生成最终客服回复")
    raw_answer = str(state.get("draft_answer", state.get("internal_answer") or state.get("answer", ""))).strip()
    if not raw_answer:
        _emit_node_complete("customer_service_rewriter", "没有可改写内容")
        return {}

    if str(state.get("answer_source", "")).strip() == "travel_plan_confirm":
        result = {
            "answer": "好的，已根据你的确认进入后续处理流程。如需调整，请随时告诉我。",
        }
        _emit_node_complete("customer_service_rewriter", "已返回确认完成文案")
        return result

    if bool(state.get("ready_for_final_confirmation")) and state.get("final_confirmation_payload"):
        _emit_node_complete("customer_service_rewriter", "已返回确认提示文案")
        return {"answer": _build_customer_friendly_confirmation_text(state.get("final_confirmation_payload", {}))}

    llm = ChatOpenAI(model="lora", base_url="http://localhost:1522/v1", api_key="123456")
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是中文智能客服总结助手。你需要基于前置节点结果和工具返回结果，输出可爱搞怪但专业、信息完整、不遗漏关键事实、带有表情的最终客服回复"
                "当用户只是补充或更新局部细节时，只回应这些细节，不要自动展开成完整计划。"
                "只有当用户明确要求完整计划、完整行程、完整安排时，才输出完整计划内容。"
                "根据问题来判断用户是否在追问历史信息，如果用户在追问历史信息，请根据历史信息给出回复。",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            (
                "user",
                "路由：{route}\n"
                "状态：{status}\n"
                "识别需求：{needs}\n"
                "上下文摘要：{context_summary}\n"
                "答案来源：{answer_source}\n"
                "校验结果：{verification}\n"
                "待确认信息：{pending_confirmation}\n\n"
                "原始业务答案：\n{raw_answer}\n\n"
                "请将它改写成最终面向用户的中文客服回复。",
            ),
        ]
    )

    messages = prompt.format_messages(
        chat_history=_normalize_history(state.get("history")),
        route=str(state.get("route", "")).strip() or "other",
        status=str(state.get("status", "completed")).strip() or "completed",
        needs=json.dumps(state.get("detected_needs", []), ensure_ascii=False),
        context_summary=str(state.get("context_summary", "")).strip() or "无",
        answer_source=str(state.get("answer_source", "")).strip() or "unknown",
        verification=json.dumps(state.get("verification", {}), ensure_ascii=False),
        pending_confirmation=json.dumps(state.get("pending_confirmation", {}), ensure_ascii=False),
        raw_answer=raw_answer,
    )

    streamed_parts: list[str] = []
    try:
        async for chunk in llm.astream(messages):
            piece = _coerce_stream_chunk_text(getattr(chunk, "content", chunk))
            if not piece:
                continue
            streamed_parts.append(piece)
            _emit_stream_event("delta", node="customer_service_rewriter", content=piece)
    except Exception as exc:
        _emit_node_error("customer_service_rewriter", str(exc).strip() or exc.__class__.__name__)
        raise

    final_answer = _strip_think_tags("".join(streamed_parts)).strip() or raw_answer
    _emit_node_complete("customer_service_rewriter", "最终客服回复生成完成")
    return {"answer": final_answer}


def summarize_result(state: ChatGraphState) -> dict[str, object]:
    _emit_node_start("summarize_result", "正在整理最终结果")
    final_answer = str(state.get("answer", "")).strip()
    final_summary = _build_final_summary_payload(state, final_answer)
    _emit_node_complete("summarize_result", "最终结果整理完成")
    return {"final_summary": final_summary}
