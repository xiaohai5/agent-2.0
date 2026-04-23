from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient

from llm.llm import read_llm
from project_config import SETTINGS


_MCP_CLIENT_CACHE: dict[str, MultiServerMCPClient] = {}
_MCP_TOOLS_CACHE: dict[str, list[Any]] = {}
_MCP_LOCKS: dict[str, asyncio.Lock] = {}
_MCP_LOCKS_GUARD = asyncio.Lock()


def _serialize_client_config(client_config: dict[str, dict[str, object]]) -> str:
    return json.dumps(client_config, ensure_ascii=False, sort_keys=True)


async def _get_cached_mcp_tools(client_config: dict[str, dict[str, object]]) -> list[Any]:
    cache_key = _serialize_client_config(client_config)
    cached = _MCP_TOOLS_CACHE.get(cache_key)
    if cached is not None:
        return cached

    async with _MCP_LOCKS_GUARD:
        lock = _MCP_LOCKS.setdefault(cache_key, asyncio.Lock())

    async with lock:
        cached = _MCP_TOOLS_CACHE.get(cache_key)
        if cached is not None:
            return cached

        client = _MCP_CLIENT_CACHE.get(cache_key)
        if client is None:
            client = MultiServerMCPClient(client_config)
            _MCP_CLIENT_CACHE[cache_key] = client

        tools = await client.get_tools()
        _MCP_TOOLS_CACHE[cache_key] = tools
        return tools


def _build_rag_knowledge_tool(user_id: int | None, top_k: int | None = None) -> Any | None:
    if user_id is None:
        return None

    collection_name = f"user_{user_id}_kb"
    retrieval_top_k = int(top_k or SETTINGS.final_top_k)

    @tool("rag_knowledge_tool")
    async def rag_knowledge_tool(query: str) -> str:
        """Search the current user's uploaded knowledge base for grounded document context."""
        query_text = str(query or "").strip()
        if not query_text:
            return "RAG query is empty."

        try:
            from llm.get_res import rag_service
            from backend.app.core.database import AsyncSessionLocal
            from backend.app.services.kg_retriever import lightweight_kg_retriever

            read_llm()
            service = rag_service({"top_k": retrieval_top_k}, collection_name=collection_name)
            text_task = asyncio.to_thread(service.get_response, query_text)
            async with AsyncSessionLocal() as db:
                text_context, kg_context = await asyncio.gather(
                    text_task,
                    lightweight_kg_retriever.retrieve(
                        db,
                        user_id=user_id,
                        query=query_text,
                        top_k=5,
                    ),
                )
            return (
                "=== 文本检索证据 ===\n"
                f"{text_context}\n\n"
                "=== 轻量知识图谱关系证据 ===\n"
                f"{kg_context}\n\n"
                "=== 使用规则 ===\n"
                "1. 文本检索证据用于回答具体事实。\n"
                "2. 轻量知识图谱关系证据用于解释实体之间的关系。\n"
                "3. 如果没有相关图谱证据，不要编造关系。\n"
                "4. 如果文本证据和图谱关系冲突，优先说明冲突并以文本证据为准。"
            )
        except Exception as exc:
            return f"RAG retrieval failed: {exc}"

    return rag_knowledge_tool


async def build_default_tools(user_id: int | None = None, top_k: int | None = None) -> list[Any]:
    from .tool_agents import build_amap_tool_agent, build_ticket_tool_agent

    ticket_agent = build_ticket_tool_agent()
    amap_agent = build_amap_tool_agent()

    @tool("ticket_12306_tool")
    async def ticket_12306_tool(request: str) -> str:
        """Send train ticket, station, schedule, fare, and availability requests to the 12306 tool agent."""
        return await ticket_agent.ask(request)

    @tool("amap_tool")
    async def amap_tool(request: str) -> str:
        """Send map, route, POI, nearby, hotel, restaurant, and scenic spot requests to the Amap tool agent."""
        return await amap_agent.ask(request)

    tools = [ticket_12306_tool, amap_tool]
    rag_tool = _build_rag_knowledge_tool(user_id=user_id, top_k=top_k)
    if rag_tool is not None:
        tools.append(rag_tool)
    return tools
