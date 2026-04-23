from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user_id
from backend.app.core.database import get_db
from backend.app.schemas.common import ApiResponse
from backend.app.schemas.feedback import DpoExportFormat, ExportFormat, FeedbackData, FeedbackSubmitRequest, FeedbackType
from backend.app.services.feedback_service import feedback_service


router = APIRouter()


@router.post("", response_model=ApiResponse[FeedbackData])
async def submit_feedback(
    payload: FeedbackSubmitRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[FeedbackData]:
    feedback = await feedback_service.submit(db, user_id, payload)
    return ApiResponse(message="ok", data=FeedbackData.model_validate(feedback))


@router.get("/export/dpo")
async def export_dpo_dataset(
    export_format: DpoExportFormat = Query(default="jsonl", alias="format"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    items = await feedback_service.list_all_for_export(db)
    rows = feedback_service.to_dpo_rows(items)

    if export_format == "json":
        content = json.dumps(rows, ensure_ascii=False, default=str)
        return Response(
            content=content,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="dpo_feedback_dataset.json"'},
        )

    if export_format == "csv":
        content = feedback_service.to_dpo_csv(rows)
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="dpo_feedback_dataset.csv"'},
        )

    content = feedback_service.to_jsonl(rows)
    return Response(
        content=content,
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="dpo_feedback_dataset.jsonl"'},
    )


@router.get("/export/all")
async def export_all_feedback(
    feedback_type: FeedbackType | None = Query(default=None),
    export_format: ExportFormat = Query(default="csv", alias="format"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    items = await feedback_service.list_all_for_export(db, feedback_type)
    rows = feedback_service.to_training_rows(items)
    filename_prefix = feedback_type or "all"

    if export_format == "json":
        content = json.dumps(rows, ensure_ascii=False, default=str)
        return Response(
            content=content,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename_prefix}_feedback.json"'},
        )

    content = feedback_service.to_csv(rows)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename_prefix}_feedback.csv"'},
    )
