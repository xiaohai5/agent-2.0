from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_mcp_adapters.client import MultiServerMCPClient

from project_config import SETTINGS

from .shared import (
    ChatGraphState,
    _build_image_items,
    _build_llm,
    _emit_node_complete,
    _emit_node_start,
    _emit_stream_event,
    _last_user_query,
    _normalize_history,
    _strip_think_tags,
)


_MCP_CLIENT_CACHE: dict[str, MultiServerMCPClient] = {}
_MCP_TOOLS_CACHE: dict[str, list[Any]] = {}
_MCP_CACHE_LOCK = asyncio.Lock()


def _serialize_client_config(client_config: dict[str, dict[str, object]]) -> str:
    return json.dumps(client_config, ensure_ascii=False, sort_keys=True)


async def _get_cached_mcp_tools(client_config: dict[str, dict[str, object]]) -> list[Any]:
    cache_key = _serialize_client_config(client_config)
    cached_tools = _MCP_TOOLS_CACHE.get(cache_key)
    if cached_tools is not None:
        return cached_tools

    async with _MCP_CACHE_LOCK:
        cached_tools = _MCP_TOOLS_CACHE.get(cache_key)
        if cached_tools is not None:
            return cached_tools

        client = _MCP_CLIENT_CACHE.get(cache_key)
        if client is None:
            client = MultiServerMCPClient(client_config)
            _MCP_CLIENT_CACHE[cache_key] = client

        tools = await client.get_tools()
        _MCP_TOOLS_CACHE[cache_key] = tools
        return tools


async def _general_answer(state: ChatGraphState, system_prompt: str) -> str:
    is_other_route = str(state.get("route", "")).strip() == "other"
    chat_history = state.get("other_history") if is_other_route else state.get("history")
    memory_summary = (
        str(state.get("other_memory_summary", "")).strip()
        if is_other_route
        else str(state.get("recent_history_summary", "")).strip()
    )

    llm = _build_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            (
                "user",
                "规则先验：{prior_routes}\n"
                "识别需求：{needs}\n"
                "上下文摘要：{context_summary}\n"
                "最近几轮对话摘要：{recent_history_summary}\n"
                "当前问题：{query}",
            ),
        ]
    )
    response = await llm.ainvoke(
        prompt.format_messages(
            chat_history=_normalize_history(chat_history),
            prior_routes="、".join(state.get("prior_routes", [])),
            needs="、".join(state.get("detected_needs", [])),
            context_summary=str(state.get("context_summary", "")).strip() or "无",
            recent_history_summary=memory_summary or "无",
            query=_last_user_query(state),
        )
    )
    return _strip_think_tags(str(getattr(response, "content", response)))


async def _run_mcp_agent(*, query: str, client_config: dict[str, dict[str, object]]) -> str:
    llm = _build_llm()
    tools = await _get_cached_mcp_tools(client_config)
    agent = create_agent(model=llm, tools=tools)
    response = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})
    messages = response.get("messages", [])
    if not messages:
        return ""
    last_message = messages[-1]
    content = getattr(last_message, "content", last_message)
    return _strip_think_tags(str(content))


def _build_ticket_query(state: ChatGraphState) -> str:
    query = _last_user_query(state)
    needs = state.get("detected_needs", [])
    context_summary = str(state.get("context_summary", "")).strip() or "无"
    return (
        "你是票务查询助手，请基于用户需求调用票务工具查询可执行方案。\n"
        "输出至少包含：车次、出发/到达时间、耗时、票价、余票、席别、注意事项。\n"
        "如果信息不足，先给当前可查到的候选方案，再说明缺什么。\n"
        "不要写成最终客服话术，只输出便于后续整合的中间结果。\n\n"
        f"用户问题：{query}\n"
        f"识别需求：{json.dumps(needs, ensure_ascii=False)}\n"
        f"上下文摘要：{context_summary}"
    )


def _build_roadmap_query(state: ChatGraphState) -> str:
    query = _last_user_query(state)
    needs = state.get("detected_needs", [])
    context_summary = str(state.get("context_summary", "")).strip() or "无"
    prior_routes = state.get("prior_routes", [])
    return (
        "你是路线规划助手，请基于用户需求调用地图工具生成详细、可执行的路线方案。\n"
        "如果是多天行程，请按天输出；如果是单段出行，请按步骤输出。\n"
        "输出至少包含：行程顺序、路线说明、交通方式、时间/距离、停留建议、住宿建议、注意事项。\n"
        "路线说明、时间距离等关键性的信息，尽量的详细。"
        "如果有图片请保留，没有图片写“图片：暂无”。\n"
        "不要写成最终客服话术，只输出便于后续统一整合的中间结果。\n\n"
        f"用户问题：{query}\n"
        f"识别需求：{json.dumps(needs, ensure_ascii=False)}\n"
        f"规则先验路由：{json.dumps(prior_routes, ensure_ascii=False)}\n"
        f"上下文摘要：{context_summary}"
    )


async def ticket(state: ChatGraphState) -> dict[str, Any]:
    raw_answer = await _run_mcp_agent(
        query=_build_ticket_query(state),
        client_config={
            "12306-mcp": {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "12306-mcp"],
            }
        },
    )
    draft_answer = raw_answer.strip()
    return {
        "draft_answer": draft_answer,
        "answer_source": "ticket_mcp",
        "image_items": _build_image_items(raw_answer) or _build_image_items(draft_answer),
    }


async def roadmap(state: ChatGraphState) -> dict[str, Any]:
    raw_answer = await _run_mcp_agent(
        query=_build_roadmap_query(state),
        client_config={
            "amap-maps-streamableHTTP": {
                "transport": "streamable_http",
                "url": "https://mcp.amap.com/mcp?key=1f8c43d66527b0fdf3c98ded711f86b7",
            }
        },
    )
    draft_answer = raw_answer.strip()
    return {
        "draft_answer": draft_answer,
        "answer_source": "roadmap_mcp",
        "image_items": _build_image_items(raw_answer),
    }


async def rag(state: ChatGraphState) -> dict[str, Any]:
    from backend.app.crued.chat import get_chat_answer

    question = _last_user_query(state)
    top_k = int(state.get("top_k") or SETTINGS.final_top_k)
    user_id = int(state.get("user_id") or 0)
    draft_answer = await asyncio.to_thread(get_chat_answer, question=question, top_k=top_k, user_id=user_id)
    return {
        "draft_answer": draft_answer,
        "answer_source": "rag_service",
        "image_items": _build_image_items(draft_answer),
    }


def _is_travel_related_query(state: ChatGraphState) -> bool:
    text = "\n".join(
        [
            str(state.get("question", "")).strip(),
            str(state.get("effective_question", "")).strip(),
            str(state.get("rewritten_question", "")).strip(),
            str(state.get("context_summary", "")).strip(),
            " ".join(str(item).strip() for item in state.get("detected_needs", []) if str(item).strip()),
        ]
    ).lower()
    travel_keywords = {
        "travel",
        "trip",
        "ticket",
        "route",
        "hotel",
        "flight",
        "train",
        "tour",
        "旅游",
        "旅行",
        "出行",
        "行程",
        "路线",
        "路程",
        "景点",
        "景区",
        "酒店",
        "住宿",
        "民宿",
        "高铁",
        "动车",
        "火车",
        "机票",
        "车票",
        "12306",
        "地铁",
        "公交",
        "打车",
        "导航",
        "攻略",
    }
    return any(keyword in text for keyword in travel_keywords)


def _extract_distance_limit_meters(query: str) -> int | None:
    normalized = str(query or "").strip().lower()
    if not normalized:
        return None
    if "1km" in normalized or "1 km" in normalized or "1公里" in normalized or "1000米" in normalized:
        return 1000
    return None


def _extract_recent_location_anchor(state: ChatGraphState) -> str:
    history = state.get("other_history") or state.get("raw_history") or state.get("history") or []
    normalized_history = _normalize_history(history)
    patterns = [
        r"我在([\u4e00-\u9fffA-Za-z0-9]{2,20}(?:站|机场|高铁站|火车站|地铁站|景区|商圈|广场|园区|大学|公园))",
        r"在([\u4e00-\u9fffA-Za-z0-9]{2,20}(?:站|机场|高铁站|火车站|地铁站|景区|商圈|广场|园区|大学|公园))",
        r"参考位置[仍然是：:\s]*([\u4e00-\u9fffA-Za-z0-9]{2,20}(?:站|机场|高铁站|火车站|地铁站|景区|商圈|广场|园区|大学|公园))",
        r"基于([\u4e00-\u9fffA-Za-z0-9]{2,20}(?:站|机场|高铁站|火车站|地铁站|景区|商圈|广场|园区|大学|公园))",
        r"([\u4e00-\u9fffA-Za-z0-9]{2,20}(?:站|机场|高铁站|火车站|地铁站|景区|商圈|广场|园区|大学|公园))",
    ]

    def _find_by_role(role: str) -> str:
        for item in reversed(normalized_history):
            if str(item.get("role", "")).strip().lower() != role:
                continue
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    candidate = str(match.group(1)).strip()
                    if candidate:
                        return candidate
        return ""

    user_anchor = _find_by_role("user")
    if user_anchor:
        return user_anchor

    assistant_anchor = _find_by_role("assistant")
    if assistant_anchor:
        return assistant_anchor

    recommendation_memory = state.get("recommendation_memory")
    if isinstance(recommendation_memory, dict):
        location_anchor = str(recommendation_memory.get("location_anchor", "")).strip()
        if location_anchor:
            return location_anchor
    return ""


def _needs_location_completion(query: str) -> bool:
    normalized = str(query or "").strip().lower()
    if not normalized:
        return False
    needs_location_keywords = {
        "餐厅",
        "饭店",
        "酒店",
        "住宿",
        "附近",
        "周边",
        "步行",
        "1000米",
        "1km",
        "1 km",
        "公里",
        "推荐",
    }
    return any(keyword in normalized for keyword in needs_location_keywords)


def _has_explicit_location(query: str) -> bool:
    text = str(query or "").strip()
    if not text:
        return False
    markers = ("我在", "在", "站", "机场", "景区", "商圈", "区", "县", "市")
    return any(marker in text for marker in markers)


def _rewrite_other_query_with_recent_context(state: ChatGraphState) -> str:
    query = _last_user_query(state)
    if not _needs_location_completion(query) or _has_explicit_location(query):
        return query

    location_anchor = _extract_recent_location_anchor(state)
    if not location_anchor:
        return query
    return f"基于{location_anchor}，{query}"


def _is_recommendation_detail_query(query: str) -> bool:
    normalized = str(query or "").strip().lower()
    if not normalized:
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
        "详细信息",
        "more details",
        "details",
    }
    return any(keyword in normalized for keyword in detail_keywords)


def _answer_detailed_from_recommendation_memory(state: ChatGraphState) -> str:
    recommendation_memory = state.get("recommendation_memory")
    if not isinstance(recommendation_memory, dict):
        return ""
    items = recommendation_memory.get("items")
    if not isinstance(items, list) or not items:
        return ""

    query = _last_user_query(state)
    if not _is_recommendation_detail_query(query):
        return ""

    normalized_query = str(query or "").strip().lower()
    want_restaurants = any(keyword in normalized_query for keyword in {"餐厅", "饭店", "restaurant"})
    want_hotels = any(keyword in normalized_query for keyword in {"酒店", "住宿", "hotel"})

    filtered_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type", "")).strip().lower()
        if want_restaurants and not want_hotels and item_type != "restaurant":
            continue
        if want_hotels and not want_restaurants and item_type != "hotel":
            continue
        filtered_items.append(item)

    if not filtered_items:
        return ""

    location_anchor = str(recommendation_memory.get("location_anchor", "")).strip()
    intro = "我先围绕上一轮已经推荐过的结果展开，不重新生成新的候选。"
    if location_anchor:
        intro += f" 参考位置仍然是{location_anchor}。"

    sections: list[str] = [intro]
    for item in filtered_items:
        name = str(item.get("name", "")).strip() or "未命名"
        item_type = str(item.get("type", "")).strip().lower()
        label = "餐厅" if item_type == "restaurant" else "酒店" if item_type == "hotel" else "地点"
        distance_m = item.get("distance_m")
        distance_text = f"{int(distance_m)}米" if isinstance(distance_m, (int, float)) else ""
        price_note = str(item.get("price_note", "")).strip()
        address_note = str(item.get("address_note", "")).strip()
        reason = str(item.get("reason", "")).strip()

        parts = [f"{name}（{label}）"]
        if distance_text:
            parts.append(f"距离约 {distance_text}")
        if price_note:
            parts.append(f"价格参考：{price_note}")
        if address_note:
            parts.append(f"位置说明：{address_note}")
        if reason:
            parts.append(f"推荐理由：{reason}")
        sections.append("；".join(parts))

    sections.append("如果你愿意，我可以继续基于这几家再帮你做一版对比，比如更适合赶车、预算更低、或者步行更近。")
    return "\n\n".join(sections)


def _answer_from_recommendation_memory(state: ChatGraphState) -> str:
    recommendation_memory = state.get("recommendation_memory")
    if not isinstance(recommendation_memory, dict):
        return ""
    items = recommendation_memory.get("items")
    if not isinstance(items, list) or not items:
        return ""

    distance_limit = _extract_distance_limit_meters(_last_user_query(state))
    if distance_limit is None:
        return ""

    matched_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        distance_m = item.get("distance_m")
        if isinstance(distance_m, (int, float)) and int(distance_m) <= distance_limit:
            matched_items.append(item)

    location_anchor = str(recommendation_memory.get("location_anchor", "")).strip()
    location_suffix = f"（参考位置：{location_anchor}）" if location_anchor else ""
    if not matched_items:
        return f"我在上轮推荐结果里没有找到明确标注为 {distance_limit} 米以内的餐厅或酒店{location_suffix}。如果你愿意，我可以按这个范围重新帮你筛一版。"

    restaurants = [item for item in matched_items if str(item.get("type", "")).strip().lower() == "restaurant"]
    hotels = [item for item in matched_items if str(item.get("type", "")).strip().lower() == "hotel"]

    def _format_items(title: str, payload: list[dict[str, Any]]) -> str:
        if not payload:
            return ""
        lines = [title]
        for item in payload:
            name = str(item.get("name", "")).strip() or "未命名"
            distance_text = f"{int(item.get('distance_m'))} 米" if isinstance(item.get("distance_m"), (int, float)) else "距离未标注"
            price_note = str(item.get("price_note", "")).strip()
            address_note = str(item.get("address_note", "")).strip()
            extras = "，".join(part for part in [distance_text, price_note, address_note] if part)
            lines.append(f"- {name}" + (f"：{extras}" if extras else ""))
        return "\n".join(lines)

    sections: list[str] = []
    restaurant_section = _format_items("1km 内的餐厅：", restaurants)
    hotel_section = _format_items("1km 内的酒店：", hotels)
    if restaurant_section:
        sections.append(restaurant_section)
    if hotel_section:
        sections.append(hotel_section)
    if not sections:
        sections.append(
            "\n".join(
                [
                    f"我找到了 {len(matched_items)} 个在 {distance_limit} 米以内的推荐项{location_suffix}：",
                    *[
                        f"- {str(item.get('name', '')).strip() or '未命名'}"
                        for item in matched_items
                    ],
                ]
            )
        )
    return "\n\n".join(sections)


async def other(state: ChatGraphState) -> dict[str, Any]:
    rewritten_query = _rewrite_other_query_with_recent_context(state)
    working_state = dict(state)
    working_state["rewritten_question"] = rewritten_query

    detailed_memory_answer = _answer_detailed_from_recommendation_memory(working_state)
    if detailed_memory_answer:
        return {
            "draft_answer": detailed_memory_answer,
            "answer_source": "recommendation_memory",
            "image_items": [],
        }

    memory_answer = _answer_from_recommendation_memory(working_state)
    if memory_answer:
        return {
            "draft_answer": memory_answer,
            "answer_source": "recommendation_memory",
            "image_items": [],
        }

    if _is_travel_related_query(working_state):
        system_prompt = (
            "你是一个通用中文助手，但当前问题与出行相关。"
            "如果用户是在问旅行建议、住宿推荐、景点推荐、出行决策或轻量规划，"
            "请给出自然、清晰、可执行的建议。"
            "除非用户明确要求完整行程或路线规划，否则不要主动输出完整旅行计划。"
        )
    else:
        system_prompt = (
            "你是一个通用中文助手。"
            "当前问题与出行无关时，不要强行往旅行、票务、路线、景点、住宿方向回答。"
            "请直接根据用户真实问题给出准确、自然、简洁的回答。"
        )

    draft_answer = await _general_answer(working_state, system_prompt)
    return {
        "draft_answer": draft_answer,
        "answer_source": "general_llm",
        "image_items": _build_image_items(draft_answer),
    }


async def _run_route_task(route: str, state: ChatGraphState) -> dict[str, Any]:
    if route == "ticket":
        return await ticket(state)
    if route == "roadmap":
        return await roadmap(state)
    if route == "rag":
        return await rag(state)
    return await other(state)


async def execute_tasks(state: ChatGraphState) -> dict[str, Any]:
    _emit_node_start("execute_tasks", "正在执行子任务")
    routes = [str(item).strip().lower() for item in state.get("subtask_routes", []) if str(item).strip()]
    if not routes:
        route = str(state.get("route", "other")).strip().lower() or "other"
        routes = [route]

    outputs: dict[str, dict[str, Any]] = {}
    draft_answer = ""
    answer_source = str(state.get("answer_source", "")).strip()
    aggregated_image_items: list[dict[str, str]] = []

    async def run_single_route(route: str) -> tuple[str, dict[str, Any]]:
        task_state = dict(state)
        task_state["route"] = route
        _emit_stream_event("route_start", route=route)
        result = await _run_route_task(route, task_state)
        return route, result if isinstance(result, dict) else {}

    route_results = await asyncio.gather(*(run_single_route(route) for route in routes))

    for route in routes:
        matched_result = next(result for result_route, result in route_results if result_route == route)
        result_image_items = [item for item in matched_result.get("image_items", []) if isinstance(item, dict)]
        outputs[route] = {
            "draft_answer": str(matched_result.get("draft_answer", matched_result.get("answer", ""))).strip(),
            "answer_source": str(matched_result.get("answer_source", route)).strip() or route,
            "image_items": result_image_items,
        }
        aggregated_image_items.extend(result_image_items)
        _emit_stream_event(
            "route_complete",
            route=route,
            answer_source=outputs[route]["answer_source"],
            has_content=bool(outputs[route]["draft_answer"]),
        )
        if not draft_answer and outputs[route]["draft_answer"]:
            draft_answer = outputs[route]["draft_answer"]
            answer_source = outputs[route]["answer_source"]

    result = {
        "task_outputs": outputs,
        "draft_answer": draft_answer,
        "answer_source": answer_source or "multi_task",
        "image_items": aggregated_image_items,
    }
    _emit_node_complete("execute_tasks", "子任务执行完成", routes=routes)
    return result
