from __future__ import annotations

from functools import lru_cache
from typing import Any


def get_user_collection_name(user_id: int) -> str:
    return f"user_{user_id}_kb"


@lru_cache(maxsize=30)
def _build_rag_service(top_k: int, collection_name: str):
    from llm.get_res import rag_service
    from llm.llm import read_llm

    read_llm()
    return rag_service({"top_k": top_k}, collection_name=collection_name)


def get_chat_answer(question: str, top_k: int, user_id: int) -> str:
    service = _build_rag_service(top_k, get_user_collection_name(user_id))
    return service.get_response(question)


async def get_agent_chat_answer(
    question: str,
    top_k: int,
    user_id: int,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    from backend.app.graphs.chat_graph import run_chat_graph

    return await run_chat_graph(
        question=question,
        top_k=top_k,
        user_id=user_id,
        history=history,
    )
