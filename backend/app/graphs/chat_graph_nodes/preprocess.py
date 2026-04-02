from __future__ import annotations

import json

from .shared import (
    _RAG_KEYWORDS,
    _ROADMAP_KEYWORDS,
    _TICKET_KEYWORDS,
    _build_context_summary_from_inherited,
    ChatGraphState,
    HISTORY_WINDOW_SIZE,
    RouteType,
    _compress_history_for_context,
    _contains_any,
    _emit_node_complete,
    _emit_node_start,
    _extract_inherited_context,
    _is_itinerary_request,
    _is_lodging_query,
    _normalize_history,
    _is_recommendation_request,
    _is_rule_knowledge_query,
    _is_scenic_query,
    _is_simple_scenic_recommendation,
    _last_user_query,
    _resolve_effective_question,
    _safe_json_llm,
    _serialize_previous_task_summary,
)


def _combined_route_text(state: ChatGraphState) -> str:
    return str(state.get("question", "")).strip().lower()


def _is_recommendation_detail_followup(state: ChatGraphState) -> bool:
    recommendation_memory = state.get("recommendation_memory")
    if not isinstance(recommendation_memory, dict):
        return False
    items = recommendation_memory.get("items")
    if not isinstance(items, list) or not items:
        return False

    text = _combined_route_text(state)
    if not text:
        return False

    detail_keywords = {
        "详细",
        "具体",
        "详情",
        "介绍",
        "展开",
        "分别",
        "说说",
        "信息",
        "刚才",
        "上面",
        "之前",
        "那几家",
        "这几家",
        "上一轮",
        "详细信息",
        "more details",
        "details",
    }
    return any(keyword in text for keyword in detail_keywords)


def _is_recommendation_memory_followup(state: ChatGraphState) -> bool:
    recommendation_memory = state.get("recommendation_memory")
    if not isinstance(recommendation_memory, dict):
        return False
    items = recommendation_memory.get("items")
    if not isinstance(items, list) or not items:
        return False

    text = _combined_route_text(state)
    if not text or len(text) > 30:
        return False

    followup_keywords = {
        "详细",
        "具体",
        "详情",
        "介绍",
        "展开",
        "分别",
        "说说",
        "信息",
        "刚才",
        "上面",
        "之前",
        "那几家",
        "这几家",
        "附近",
        "周边",
        "1km",
        "1 km",
        "1公里",
        "1000米",
        "步行",
        "更近",
        "餐厅",
        "饭店",
        "酒店",
        "住宿",
    }
    return any(keyword in text for keyword in followup_keywords)


def _deterministic_route(state: ChatGraphState) -> RouteType | None:
    text = _combined_route_text(state)
    if not text:
        return None

    ticket_keywords = set(_TICKET_KEYWORDS) | {
        "高铁",
        "动车",
        "火车",
        "高铁票",
        "动车票",
        "火车票",
        "车票",
        "余票",
        "车次",
    }
    strong_roadmap_keywords = {
        "路线",
        "线路",
        "行程",
        "攻略",
        "规划",
        "游玩顺序",
        "一日游路线",
        "两天一夜行程",
        "itinerary",
    }
    weak_roadmap_keywords = set(_ROADMAP_KEYWORDS) | {"安排", "一日游", "两天一夜", "半日游", "怎么玩"}
    lodging_keywords = {
        "住哪里",
        "住哪",
        "住哪个区",
        "酒店推荐",
        "住宿推荐",
        "住宿建议",
        "酒店建议",
        "附近住宿",
    }
    other_keywords = {
        "预算",
        "多少钱",
        "费用",
        "花费",
        "带老人",
        "亲子",
        "带孩子",
        "轻松",
        "省心",
        "推荐",
    }

    has_ticket = _contains_any(text, ticket_keywords)
    has_strong_roadmap = _contains_any(text, strong_roadmap_keywords)
    has_weak_roadmap = _contains_any(text, weak_roadmap_keywords)
    has_lodging = _contains_any(text, lodging_keywords)
    has_rule_knowledge = _is_rule_knowledge_query(text)
    has_other = _contains_any(text, other_keywords)
    is_simple_scenic_recommendation = _is_simple_scenic_recommendation(text)

    if has_rule_knowledge:
        return "rag"
    if has_ticket:
        return "ticket"
    if is_simple_scenic_recommendation:
        return "other"
    if has_strong_roadmap:
        return "roadmap"
    if has_weak_roadmap and not has_lodging:
        return "roadmap"
    if has_other:
        return "other"
    return None


def _determine_primary_intent(state: ChatGraphState) -> str:
    text = _combined_route_text(state)
    if not text:
        return "other"
    if _is_recommendation_detail_followup(state) or _is_recommendation_memory_followup(state):
        return "recommendation"

    asks_full_plan = _is_itinerary_request(text) or _contains_any(text, {"完整行程", "完整计划", "出行计划", "旅游计划"})
    asks_rag = _is_rule_knowledge_query(text)
    asks_ticket = _contains_any(text, _TICKET_KEYWORDS) or _contains_any(text, {"高铁", "动车", "火车", "车票", "余票", "车次"})
    asks_lodging = _is_lodging_query(text)
    asks_scenic = _is_scenic_query(text)
    asks_recommendation = _is_recommendation_request(text)

    if asks_full_plan and (asks_ticket or asks_lodging or asks_scenic):
        return "travel_plan"
    if asks_rag and not asks_full_plan:
        return "rag"
    if asks_ticket and not asks_full_plan and not asks_lodging and not asks_scenic:
        return "ticket"
    if asks_scenic and asks_recommendation and not asks_full_plan:
        return "recommendation"
    return _deterministic_route(state) or "other"


def _determine_subtask_routes(state: ChatGraphState, primary_intent: str) -> list[str]:
    text = _combined_route_text(state)
    routes: list[str] = []

    if primary_intent == "travel_plan":
        routes.append("roadmap")
        if _contains_any(text, _TICKET_KEYWORDS) or _contains_any(text, {"高铁", "动车", "火车", "车票", "余票", "车次"}):
            routes.append("ticket")
        return routes

    if primary_intent == "rag":
        return ["rag"]
    if primary_intent == "recommendation":
        return ["other"]

    routes.append(_deterministic_route(state) or "other")

    deduped: list[str] = []
    for route in routes:
        if route not in deduped:
            deduped.append(route)
    return deduped or ["other"]


def _execution_order(primary_intent: str, routes: list[str]) -> list[str]:
    if primary_intent == "travel_plan":
        priority = {"roadmap": 0, "ticket": 1, "rag": 2, "other": 3}
        return sorted(routes, key=lambda item: priority.get(item, 99))
    return routes


def _rule_based_prior_routes(state: ChatGraphState) -> list[str]:
    text = _combined_route_text(state)
    hits: list[str] = []
    deterministic_route = _deterministic_route(state)
    if deterministic_route:
        hits.append(deterministic_route)
    if "ticket" not in hits and any(keyword.lower() in text for keyword in _TICKET_KEYWORDS):
        hits.append("ticket")
    if "roadmap" not in hits and any(keyword.lower() in text for keyword in _ROADMAP_KEYWORDS):
        hits.append("roadmap")
    if "rag" not in hits and any(keyword.lower() in text for keyword in _RAG_KEYWORDS):
        hits.append("rag")
    if not hits:
        hits.append("other")
    return hits


def _extract_needs(state: ChatGraphState) -> list[str]:
    question = _last_user_query(state)
    if not question:
        return []

    try:
        parsed = _safe_json_llm(
            system_prompt=(
                "你是需求提取助手。"
                "给定用户问题、路由提示以及可选的上一轮任务摘要，"
                "请只返回 JSON，且只包含一个字段：detected_needs。"
                "detected_needs 必须是简洁字符串数组，不要补充没有依据的假设。"
            ),
            user_prompt=(
                f"候选路由：{json.dumps(state.get('prior_routes', []), ensure_ascii=False)}\n"
                f"上一轮任务摘要：{_serialize_previous_task_summary(state.get('previous_task_summary', {}))}\n"
                f"当前问题：{question}"
            ),
            history=state.get("history"),
        )
    except Exception:
        return [question]

    needs = parsed.get("detected_needs", []) if isinstance(parsed, dict) else []
    normalized = [str(item).strip() for item in needs if str(item).strip()]
    return normalized or [question]


def _summarize_and_rewrite(state: ChatGraphState, detected_needs: list[str]) -> tuple[str, str]:
    question = str(state.get("question", "")).strip()
    inherited_context = state.get("inherited_context", {}) if isinstance(state.get("inherited_context"), dict) else {}
    inherited_context_summary = _build_context_summary_from_inherited(inherited_context)
    try:
        parsed = _safe_json_llm(
            system_prompt=(
                "你是上下文摘要与问题改写助手。"
                "请只返回 JSON，包含两个字段：context_summary 和 rewritten_question。"
                "要始终优先保留当前问题的核心意图。"
                "只有在确实需要补足指代、省略或缺失约束时，才最小化使用上文。"
                "除非当前问题明确要求延续上一轮业务，否则不要把当前问题扩展成上一轮的领域任务。"
                "如果当前问题是在问对话本身或历史内容，就保持为对话/历史问题，不要改写成业务任务。"
                "context_summary 应尽量简短，只保留当前问题真正需要的上下文。"
                "rewritten_question 应尽量贴近用户原话，同时方便下游处理。"
            ),
            user_prompt=(
                f"候选路由：{json.dumps(state.get('prior_routes', []), ensure_ascii=False)}\n"
                f"上一轮任务摘要：{_serialize_previous_task_summary(state.get('previous_task_summary', {}))}\n"
                f"继承模式：{str(state.get('inherit_mode', 'none')).strip() or 'none'}\n"
                f"允许继承字段：{json.dumps(state.get('carry_fields', []), ensure_ascii=False)}\n"
                f"已继承上下文：{json.dumps(inherited_context, ensure_ascii=False)}\n"
                f"最近几轮对话摘要：{str(state.get('recent_history_summary', '')).strip()}\n"
                f"当前问题：{question}\n"
                f"识别到的需求：{json.dumps(detected_needs, ensure_ascii=False)}\n"
                "改写约束：\n"
                "1. 保持当前问题主意图不变。\n"
                "2. 只有在继承模式不是 none 且确有必要时，才注入上文。\n"
                "3. 除非当前问题明确继续上一任务，否则不要继承上一任务的领域、路由或目标。\n"
                "4. 优先做最小必要补全，不要过度扩写。\n"
                "5. 如果当前问题是在问聊天记录、前文内容或历史说法，保持为对话历史问题。\n"
                "6. 当继承模式为 none 时，context_summary 通常应为空，或只描述当前问题。"
            ),
            history=state.get("history"),
        )
    except Exception:
        return inherited_context_summary, question

    context_summary = str(parsed.get("context_summary", "")).strip() if isinstance(parsed, dict) else inherited_context_summary
    rewritten_question = str(parsed.get("rewritten_question", "")).strip() if isinstance(parsed, dict) else ""
    if inherited_context_summary and not context_summary and str(state.get("inherit_mode", "none")).strip() != "none":
        context_summary = inherited_context_summary
    return context_summary, rewritten_question or question


def preprocess_query(state: ChatGraphState) -> dict[str, object]:
    _emit_node_start("preprocess_query", "正在分析问题和上下文")
    effective_question, confirmed, pending_confirmation, previous_task_summary, inheritance = _resolve_effective_question(state)
    fallback_question = effective_question
    prior_routes = _rule_based_prior_routes(state)
    inherit_mode = str(inheritance.get("inherit_mode", "none")).strip() or "none"
    carry_fields = [str(item).strip() for item in inheritance.get("carry_fields", []) if str(item).strip()]
    carry_context = inherit_mode != "none"
    recent_history, overflow_history_summary = _compress_history_for_context(
        state.get("history"),
        keep_last=HISTORY_WINDOW_SIZE,
    )
    history_for_preprocess = recent_history
    history_for_downstream = []
    inherited_context = _extract_inherited_context(previous_task_summary, carry_fields) if carry_context else {}
    recommendation_memory = (
        inherited_context.get("recommendation_memory")
        if isinstance(inherited_context.get("recommendation_memory"), dict)
        else {}
    )
    recent_history_summary = overflow_history_summary
    other_history = recent_history
    other_memory_summary = overflow_history_summary

    working_state: ChatGraphState = dict(state)
    working_state["question"] = effective_question
    working_state["effective_question"] = effective_question
    working_state["prior_routes"] = prior_routes
    working_state["previous_task_summary"] = previous_task_summary if carry_context else {}
    working_state["inherit_mode"] = inherit_mode
    working_state["carry_fields"] = carry_fields
    working_state["inherit_reason"] = str(inheritance.get("reason", "")).strip()
    working_state["inherited_context"] = inherited_context
    working_state["recommendation_memory"] = recommendation_memory
    working_state["recent_history_summary"] = recent_history_summary
    working_state["other_history"] = other_history
    working_state["other_memory_summary"] = other_memory_summary
    working_state["history"] = history_for_preprocess

    detected_needs = _extract_needs(working_state)
    normalized_needs = detected_needs or ([fallback_question] if fallback_question else [])
    normalized_summary, normalized_question = _summarize_and_rewrite(working_state, normalized_needs)

    result = {
        "effective_question": effective_question,
        "confirmed": confirmed,
        "pending_confirmation": pending_confirmation,
        "raw_history": _normalize_history(state.get("history")),
        "history": history_for_downstream,
        "previous_task_summary": previous_task_summary if carry_context else {},
        "carry_context": carry_context,
        "inherit_mode": inherit_mode,
        "carry_fields": carry_fields,
        "inherit_reason": str(inheritance.get("reason", "")).strip(),
        "inherited_context": inherited_context,
        "recommendation_memory": recommendation_memory,
        "recent_history_summary": recent_history_summary,
        "other_history": other_history,
        "other_memory_summary": other_memory_summary,
        "status": "completed",
        "prior_routes": prior_routes,
        "detected_needs": normalized_needs,
        "context_summary": normalized_summary,
        "rewritten_question": normalized_question,
    }
    _emit_node_complete(
        "preprocess_query",
        "已完成预处理",
        rewritten_question=normalized_question,
        detected_needs=normalized_needs,
        inherit_mode=inherit_mode,
    )
    return result


def agent_manager(state: ChatGraphState) -> dict[str, object]:
    _emit_node_start("agent_manager", "正在确定任务路由")
    primary_intent = _determine_primary_intent(state)
    subtask_routes = _execution_order(primary_intent, _determine_subtask_routes(state, primary_intent))
    route = subtask_routes[0] if subtask_routes else "other"
    result = {
        "primary_intent": primary_intent,
        "subtask_routes": subtask_routes,
        "route": route,
    }
    _emit_node_complete("agent_manager", "已完成任务路由", primary_intent=primary_intent, routes=subtask_routes)
    return result
