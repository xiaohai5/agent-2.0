from __future__ import annotations

import json
from typing import Any

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from llm.llm import read_llm
from project_config import SETTINGS

from .tools import _get_cached_mcp_tools


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return str(value)


def _decode_jsonish(value: Any) -> list[Any]:
    value = _jsonable(value)
    if isinstance(value, list):
        decoded: list[Any] = []
        for item in value:
            decoded.extend(_decode_jsonish(item))
        return decoded
    if isinstance(value, dict):
        text_value = value.get("text")
        if isinstance(text_value, str):
            decoded_text = _decode_jsonish(text_value)
            if decoded_text:
                return decoded_text
        return [value]
    if not isinstance(value, str):
        return [{"text": str(value)}]

    text = value.strip()
    if not text:
        return []

    try:
        return [json.loads(text)]
    except (json.JSONDecodeError, ValueError):
        return [{"text": text}]


class MCPToolAgent:
    def __init__(self, name: str, client_config: dict[str, dict[str, object]], system_prompt: str) -> None:
        self.name = name
        self.client_config = client_config
        self.system_prompt = system_prompt
        self._agent: Any | None = None

    async def _get_agent(self) -> Any:
        if self._agent is None:
            read_llm()
            llm = ChatOpenAI(model=SETTINGS.llm_model, temperature=0)
            tools = await _get_cached_mcp_tools(self.client_config)
            self._agent = create_agent(model=llm, tools=tools)
        return self._agent

    async def ask(self, request: str) -> str:
        agent = await self._get_agent()
        response = await agent.ainvoke(
            {
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": request},
                ]
            }
        )
        messages = response.get("messages", []) if isinstance(response, dict) else []

        tool_results: list[dict[str, Any]] = []
        for message in messages:
            if getattr(message, "type", "") != "tool":
                continue
            content = getattr(message, "content", "")
            tool_results.append(
                {
                    "tool_name": getattr(message, "name", ""),
                    "results": _decode_jsonish(content),
                    "raw": _jsonable(content),
                }
            )

        if messages:
            final_answer = getattr(messages[-1], "content", messages[-1])
        else:
            final_answer = getattr(response, "content", response)

        payload = {
            "source_agent": self.name,
            "request": request,
            "data": tool_results,
            "final_answer": _jsonable(final_answer),
        }
        return json.dumps(payload, ensure_ascii=False)


def build_ticket_tool_agent() -> MCPToolAgent:
    return MCPToolAgent(
        name="ticket_12306_agent",
        client_config={
            "12306-mcp": {
                "transport": "stdio",
                "command": SETTINGS.ticket_mcp_command,
                "args": list(SETTINGS.ticket_mcp_args),
            }
        },
        system_prompt=(
            "你是 12306 工具 Agent。只负责火车票、车次、余票、票价、站点、列车时刻等信息查询。"
            "根据交流 Agent 的请求选择并调用可用 MCP 工具，返回准确、简洁、可供上游整合的结果。"
        ),
    )


def build_amap_tool_agent() -> MCPToolAgent:
    return MCPToolAgent(
        name="amap_agent",
        client_config={
            "amap-maps-streamableHTTP": {
                "transport": "streamable_http",
                "url": SETTINGS.amap_mcp_url,
            }
        },
        system_prompt=(
            "你是高德地图工具 Agent。只负责地图、路线、地理编码、POI、周边、酒店、餐厅、景点等位置服务查询。"
            "根据交流 Agent 的请求选择并调用可用 MCP 工具，返回准确、简洁、可供上游整合的结果。"
        ),
    )
