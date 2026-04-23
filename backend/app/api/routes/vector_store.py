from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user_id
from backend.app.core.database import get_db
from backend.app.schemas.common import ApiResponse
from backend.app.schemas.vector_store import DocumentItem, GraphSummaryData, UploadData
from backend.app.services.document_service import document_service


router = APIRouter()


@router.post("/upload", response_model=ApiResponse[UploadData], status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UploadData]:
    payload = await document_service.upload(
        db=db,
        user_id=user_id,
        filename=file.filename or "unnamed.txt",
        file_bytes=await file.read(),
    )
    return ApiResponse(
        message="文档上传成功",
        data=UploadData(**payload),
    )


@router.get("/documents", response_model=ApiResponse[list[DocumentItem]])
async def list_documents(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
) -> ApiResponse[list[DocumentItem]]:
    items = await document_service.list_documents(db, user_id)
    return ApiResponse(message="文档列表获取成功", data=items)


@router.get("/graph", response_model=ApiResponse[GraphSummaryData])
async def get_graph_summary(
    filename: str | None = Query(default=None),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[GraphSummaryData]:
    payload = await document_service.graph_summary(db=db, user_id=user_id, filename=filename)
    return ApiResponse(message="GraphRAG demo graph loaded.", data=GraphSummaryData(**payload))


@router.delete("/documents", response_model=ApiResponse[UploadData])
async def delete_document(
    filename: str = Query(..., min_length=1),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UploadData]:
    payload = await document_service.delete(db=db, user_id=user_id, filename=filename)
    return ApiResponse(message="文档删除成功", data=UploadData(status="deleted", **payload))
