from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph

from .chat_graph_nodes.confirmation import after_confirmation_gate, await_confirmation, confirmation_gate
from .chat_graph_nodes.preprocess import agent_manager, preprocess_query
from .chat_graph_nodes.response import after_execute_tasks, compose_answer, customer_service_rewriter, other_route_rewriter, summarize_result, verify_answer
from .chat_graph_nodes.shared import ChatGraphState, _normalize_history, reset_stream_queue, set_stream_queue
from .chat_graph_nodes.tasks import execute_tasks


@lru_cache(maxsize=1)
def build_chat_graph():
    builder: StateGraph[ChatGraphState] = StateGraph(ChatGraphState)
    builder.add_node("preprocess_query", preprocess_query)
    builder.add_node("agent_manager", agent_manager)
    builder.add_node("confirmation_gate", confirmation_gate)
    builder.add_node("await_confirmation", await_confirmation)
    builder.add_node("execute_tasks", execute_tasks)
    builder.add_node("other_route_rewriter", other_route_rewriter)
    builder.add_node("compose_answer", compose_answer)
    builder.add_node("verify_answer", verify_answer)
    builder.add_node("customer_service_rewriter", customer_service_rewriter)
    builder.add_node("summarize_result", summarize_result)

    builder.add_edge(START, "preprocess_query")
    builder.add_edge("preprocess_query", "agent_manager")
    builder.add_edge("agent_manager", "confirmation_gate")
    builder.add_conditional_edges(
        "confirmation_gate",
        after_confirmation_gate,
        ["await_confirmation", "execute_tasks", END],
    )
    builder.add_edge("await_confirmation", "customer_service_rewriter")
    builder.add_conditional_edges(
        "execute_tasks",
        after_execute_tasks,
        ["other_route_rewriter", "compose_answer"],
    )
    builder.add_edge("other_route_rewriter", END)
    builder.add_edge("compose_answer", "verify_answer")
    builder.add_edge("verify_answer", "customer_service_rewriter")
    builder.add_edge("customer_service_rewriter", "summarize_result")
    builder.add_edge("summarize_result", END)
    return builder.compile()


graph = build_chat_graph()


async def run_chat_graph(
    question: str,
    top_k: int,
    user_id: int,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result = await graph.ainvoke(
        {
            "question": question,
            "history": _normalize_history(history),
            "top_k": top_k,
            "user_id": user_id,
        }
    )
    pending_confirmation = result.get("pending_confirmation")
    return {
        "answer": str(result.get("answer", "")).strip(),
        "status": str(result.get("status", "completed")).strip() or "completed",
        "pending_confirmation": pending_confirmation if isinstance(pending_confirmation, dict) and pending_confirmation else None,
        "final_summary": result.get("final_summary", {}),
    }


async def run_chat_graph_stream(
    question: str,
    top_k: int,
    user_id: int,
    history: list[dict[str, Any]] | None = None,
):
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    token = set_stream_queue(queue)
    task = asyncio.create_task(
        run_chat_graph(
            question=question,
            top_k=top_k,
            user_id=user_id,
            history=history,
        )
    )

    try:
        while True:
            if task.done() and queue.empty():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.1)
            except TimeoutError:
                continue
            yield event

        result = await task
        yield {"type": "graph_complete", "payload": result}
    finally:
        reset_stream_queue(token)
