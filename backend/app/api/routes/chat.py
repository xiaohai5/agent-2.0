from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user_id
from backend.app.core.database import get_db
from backend.app.schemas.chat import ChatData, ChatMessage, ChatRequest
from backend.app.schemas.common import ApiResponse
from backend.app.services.dual_agent_service import dual_agent_chat_service


router = APIRouter()


@router.post("/completion", response_model=ApiResponse[ChatData])
async def chat_completion(
    payload: ChatRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ChatData]:
    result = await dual_agent_chat_service.answer(
        db=db,
        user_id=user_id,
        question=payload.question,
        top_k=payload.top_k,
        history=[message.model_dump() for message in payload.history],
    )
    data = ChatData(
        answer=result["answer"],
        history=[ChatMessage(**item) for item in result["history"]],
        status=result["status"],
        conversation_id=payload.conversation_id,
        route=result.get("route", "chat"),
        model=result.get("model"),
        tool_calls=result.get("tool_calls"),
        answer_source=result.get("answer_source"),
    )
    return ApiResponse(message="对话完成", data=data)


@router.post("/completion/stream")
async def chat_completion_stream(
    payload: ChatRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    history = [message.model_dump() for message in payload.history]

    async def event_stream():
        try:
            yield (json.dumps({"type": "status", "message": "processing"}, ensure_ascii=False) + "\n").encode("utf-8")
            async for event in dual_agent_chat_service.answer_stream(
                db=db,
                user_id=user_id,
                question=payload.question,
                top_k=payload.top_k,
                history=history,
            ):
                event_type = str(event.get("type", "")).strip().lower()
                if event_type == "status":
                    yield (json.dumps({"type": "status", "message": event.get("message", "")}, ensure_ascii=False) + "\n").encode("utf-8")
                    continue
                if event_type == "chunk":
                    yield (json.dumps({"type": "chunk", "content": event.get("content", "")}, ensure_ascii=False) + "\n").encode("utf-8")
                    continue
                if event_type == "done":
                    data = event.get("payload", {})
                    if isinstance(data, dict):
                        data = {**data, "conversation_id": payload.conversation_id}
                    yield (
                        json.dumps(
                            {
                                "type": "done",
                                "payload": {
                                    "code": 0,
                                    "message": "对话完成",
                                    "data": data,
                                },
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    ).encode("utf-8")
                    return
        except Exception as exc:
            yield (json.dumps({"type": "error", "detail": str(exc)}, ensure_ascii=False) + "\n").encode("utf-8")

    return StreamingResponse(event_stream(), media_type="application/x-ndjson; charset=utf-8")
