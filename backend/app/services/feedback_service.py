from __future__ import annotations

import csv
import io
import json
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.feedback import MessageFeedback
from backend.app.schemas.feedback import FeedbackSubmitRequest, FeedbackType


EXPORT_FIELDS = (
    "conversation_id",
    "message_id",
    "user_message",
    "ai_message",
    "feedback_type",
    "created_at",
    "route",
    "model",
    "tool_calls",
    "answer_source",
)

DPO_EXPORT_FIELDS = (
    "prompt",
    "chosen",
    "rejected",
    "conversation_id",
    "chosen_message_id",
    "rejected_message_id",
    "route",
    "model",
    "chosen_created_at",
    "rejected_created_at",
    "metadata",
)


class FeedbackService:
    async def submit(
        self,
        db: AsyncSession,
        user_id: int,
        payload: FeedbackSubmitRequest,
    ) -> MessageFeedback:
        result = await db.execute(
            select(MessageFeedback).where(
                MessageFeedback.user_id == user_id,
                MessageFeedback.message_id == payload.message_id,
            )
        )
        feedback = result.scalar_one_or_none()

        if feedback:
            feedback.conversation_id = payload.conversation_id
            feedback.user_message = payload.user_message
            feedback.ai_message = payload.ai_message
            feedback.feedback_type = payload.feedback_type
            feedback.route = payload.route
            feedback.model = payload.model
            feedback.tool_calls = payload.tool_calls
            feedback.answer_source = payload.answer_source
            await db.flush()
            await db.refresh(feedback)
            return feedback

        feedback = MessageFeedback(
            user_id=user_id,
            conversation_id=payload.conversation_id,
            message_id=payload.message_id,
            user_message=payload.user_message,
            ai_message=payload.ai_message,
            feedback_type=payload.feedback_type,
            route=payload.route,
            model=payload.model,
            tool_calls=payload.tool_calls,
            answer_source=payload.answer_source,
        )
        db.add(feedback)
        await db.flush()
        await db.refresh(feedback)
        return feedback

    async def list_all_for_export(
        self,
        db: AsyncSession,
        feedback_type: FeedbackType | None = None,
    ) -> list[MessageFeedback]:
        statement = select(MessageFeedback)
        if feedback_type:
            statement = statement.where(MessageFeedback.feedback_type == feedback_type)
        statement = statement.order_by(MessageFeedback.created_at.asc(), MessageFeedback.id.asc())
        result = await db.execute(statement)
        return list(result.scalars().all())

    def to_training_rows(self, feedback_items: Iterable[MessageFeedback]) -> list[dict[str, Any]]:
        return [
            {
                "conversation_id": item.conversation_id,
                "message_id": item.message_id,
                "user_id": item.user_id,
                "user_message": item.user_message,
                "ai_message": item.ai_message,
                "feedback_type": item.feedback_type,
                "created_at": item.created_at.isoformat() if item.created_at else "",
                "route": item.route,
                "model": item.model or "",
                "tool_calls": item.tool_calls,
                "answer_source": item.answer_source,
            }
            for item in feedback_items
        ]

    def to_csv(self, rows: list[dict[str, Any]]) -> str:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "tool_calls": json.dumps(row.get("tool_calls"), ensure_ascii=False) if row.get("tool_calls") is not None else "",
                    "answer_source": json.dumps(row.get("answer_source"), ensure_ascii=False) if row.get("answer_source") is not None else "",
                }
            )
        return buffer.getvalue()

    def to_dpo_rows(self, feedback_items: Iterable[MessageFeedback]) -> list[dict[str, Any]]:
        liked: dict[tuple[str, str], list[MessageFeedback]] = {}
        disliked: dict[tuple[str, str], list[MessageFeedback]] = {}

        for item in feedback_items:
            key = (self._normalize_prompt(item.user_message), item.route or "chat")
            if item.feedback_type == "like":
                liked.setdefault(key, []).append(item)
            if item.feedback_type == "dislike":
                disliked.setdefault(key, []).append(item)

        rows: list[dict[str, Any]] = []
        for key, chosen_items in liked.items():
            rejected_items = disliked.get(key, [])
            for chosen, rejected in zip(chosen_items, rejected_items):
                prompt = chosen.user_message
                rows.append(
                    {
                        "prompt": prompt,
                        "chosen": chosen.ai_message,
                        "rejected": rejected.ai_message,
                        "chosen_messages": [
                            {"role": "user", "content": prompt},
                            {"role": "assistant", "content": chosen.ai_message},
                        ],
                        "rejected_messages": [
                            {"role": "user", "content": prompt},
                            {"role": "assistant", "content": rejected.ai_message},
                        ],
                        "conversation_id": chosen.conversation_id,
                        "chosen_message_id": chosen.message_id,
                        "rejected_message_id": rejected.message_id,
                        "chosen_user_id": chosen.user_id,
                        "rejected_user_id": rejected.user_id,
                        "route": chosen.route,
                        "model": chosen.model or rejected.model or "",
                        "chosen_created_at": chosen.created_at.isoformat() if chosen.created_at else "",
                        "rejected_created_at": rejected.created_at.isoformat() if rejected.created_at else "",
                        "metadata": {
                            "chosen_feedback_type": chosen.feedback_type,
                            "rejected_feedback_type": rejected.feedback_type,
                            "chosen_conversation_id": chosen.conversation_id,
                            "rejected_conversation_id": rejected.conversation_id,
                            "chosen_tool_calls": chosen.tool_calls,
                            "rejected_tool_calls": rejected.tool_calls,
                            "chosen_answer_source": chosen.answer_source,
                            "rejected_answer_source": rejected.answer_source,
                        },
                    }
                )
        return rows

    def to_jsonl(self, rows: list[dict[str, Any]]) -> str:
        return "\n".join(json.dumps(row, ensure_ascii=False, default=str) for row in rows)

    def to_dpo_csv(self, rows: list[dict[str, Any]]) -> str:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=DPO_EXPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "metadata": json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                }
            )
        return buffer.getvalue()

    def _normalize_prompt(self, prompt: str) -> str:
        return " ".join(prompt.strip().split())


feedback_service = FeedbackService()
