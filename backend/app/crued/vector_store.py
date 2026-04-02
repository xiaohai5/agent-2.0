from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.models.vector_store import DocumentItem


async def create_document_record(
    user_id: int,
    filename: str,
    db: AsyncSession = Depends(get_db),
) -> DocumentItem:
    record = DocumentItem(
        user_id=user_id,
        filename=filename,
        status="recorded",
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_documents_by_user_id(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[DocumentItem]:
    result = await db.execute(
        select(DocumentItem)
        .where(DocumentItem.user_id == user_id)
        .order_by(DocumentItem.id.desc())
    )
    return list(result.scalars().all())


async def delete_document_records(
    user_id: int,
    filename: str,
    db: AsyncSession = Depends(get_db),
) -> int:
    result = await db.execute(
        delete(DocumentItem)
        .where(DocumentItem.user_id == user_id)
        .where(DocumentItem.filename == filename)
    )
    await db.commit()
    return int(result.rowcount or 0)
