from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import StreamingResponse

from backend.app.core.database import AsyncSessionLocal
from backend.app.crued.chat import get_agent_chat_answer
from backend.app.graphs.chat_graph_nodes.shared import _compress_history_for_storage
from backend.app.crued.user import verify_token
from backend.app.schemas.chat import ChatMessage, ChatRequest, ChatResponse
from backend.app.utils.user import parse_bearer_token


router = APIRouter()
logger = logging.getLogger(__name__)


def _flatten_exception_messages(exc: BaseException) -> list[str]:
    if isinstance(exc, BaseExceptionGroup):
        messages: list[str] = []
        for child in exc.exceptions:
            messages.extend(_flatten_exception_messages(child))
        return messages

    message = str(exc).strip()
    if not message and getattr(exc, "__cause__", None):
        return _flatten_exception_messages(exc.__cause__)
    return [message or exc.__class__.__name__]


def _build_error_detail(exc: Exception) -> str:
    parts = [part for part in _flatten_exception_messages(exc) if part]
    deduped: list[str] = []
    for part in parts:
        if part not in deduped:
            deduped.append(part)
    joined = " | ".join(deduped)
    return joined or exc.__class__.__name__


def _friendly_error_detail(exc: Exception) -> str:
    detail = _build_error_detail(exc)
    lowered = detail.lower()
    exc_name = exc.__class__.__name__.lower()

    if "apiconnectionerror" in lowered or "connection error" in lowered or "connect" in exc_name:
        return f"{detail} | 请检查 OPENAI_BASE_URL、代理地址或当前网络连通性"
    if "timeout" in lowered or "timeout" in exc_name:
        return f"{detail} | 上游 LLM 请求超时，请稍后重试"
    if "authentication" in lowered or "invalid api key" in lowered or "unauthorized" in lowered:
        return f"{detail} | 请检查 OPENAI_API_KEY / OPENAI_API_KEY1 是否正确"
    if "ratelimit" in lowered or "rate limit" in lowered or "429" in lowered:
        return f"{detail} | 上游 LLM 限流，请稍后重试"
    return detail


def _build_chat_response_payload(payload: ChatRequest, result: dict[str, object]) -> ChatResponse:
    reply = str(result.get("answer", "")).strip()
    status_value = str(result.get("status", "completed")).strip().lower()
    status_name = "needs_confirmation" if status_value == "needs_confirmation" else "completed"
    pending_confirmation = result.get("pending_confirmation")
    final_summary = result.get("final_summary")
    assistant_metadata: dict[str, object] = {}
    if isinstance(pending_confirmation, dict) and pending_confirmation:
        assistant_metadata["pending_confirmation"] = pending_confirmation
    if isinstance(final_summary, dict) and final_summary:
        assistant_metadata["final_summary"] = final_summary

    history = payload.history + [
        ChatMessage(role="user", content=payload.question),
        ChatMessage(role="assistant", content=reply, metadata=assistant_metadata),
    ]
    compressed_history = _compress_history_for_storage([message.model_dump() for message in history])
    return ChatResponse(
        answer=reply,
        history=[ChatMessage(**message) for message in compressed_history],
        status=status_name,
        pending_confirmation=pending_confirmation if isinstance(pending_confirmation, dict) else None,
        final_summary=final_summary if isinstance(final_summary, dict) else None,
    )


@router.post("/completion", response_model=ChatResponse)
async def chat_completion(
    payload: ChatRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> ChatResponse:
    token = parse_bearer_token(authorization)
    async with AsyncSessionLocal() as db:
        user_id = await verify_token(token, db)

    try:
        history_payload = [message.model_dump() for message in payload.history]
        result = await get_agent_chat_answer(
            payload.question,
            payload.top_k,
            user_id,
            history_payload,
        )
    except Exception as exc:
        logger.exception("chat_completion failed for user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM generation failed: {_friendly_error_detail(exc)}",
        ) from exc

    return _build_chat_response_payload(payload, result)


@router.post("/completion/stream")
async def chat_completion_stream(
    payload: ChatRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> StreamingResponse:
    token = parse_bearer_token(authorization)
    async with AsyncSessionLocal() as db:
        user_id = await verify_token(token, db)

    async def event_stream():
        def make_event(event_type: str, **data: object) -> bytes:
            return (json.dumps({"type": event_type, **data}, ensure_ascii=False) + "\n").encode("utf-8")

        yield make_event("status", message="starting")
        try:
            from backend.app.graphs.chat_graph import run_chat_graph_stream

            history_payload = [message.model_dump() for message in payload.history]
            async for event in run_chat_graph_stream(
                question=payload.question,
                top_k=payload.top_k,
                user_id=user_id,
                history=history_payload,
            ):
                event_type = str(event.get("type", "")).strip().lower()
                if event_type == "graph_complete":
                    result = event.get("payload")
                    response_payload = _build_chat_response_payload(payload, result if isinstance(result, dict) else {})
                    yield make_event("done", payload=response_payload.model_dump())
                    continue
                yield make_event(event_type or "status", **{k: v for k, v in event.items() if k != "type"})
        except Exception as exc:
            logger.exception("chat_completion_stream failed for user_id=%s", user_id)
            yield make_event(
                "error",
                detail=f"LLM generation failed: {_friendly_error_detail(exc)}",
            )

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
