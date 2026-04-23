"""
文档相关的数据库 CRUD 操作
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.vector_store import DocumentItem


ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "backend" / "data"
UPLOAD_DIR = DATA_DIR / "uploads"


def utc_now() -> datetime:
    """返回当前 UTC 时间（naive datetime，与数据库一致）"""
    return datetime.utcnow()


async def save_document(
    db: AsyncSession,
    user_id: int,
    filename: str,
    file_bytes: bytes,
    extracted_text: str,
    status: str = "recorded"
) -> DocumentItem:
    """保存文档记录和文件"""
    # 确保目录存在
    user_dir = UPLOAD_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    # 保存原始文件
    suffix = Path(filename).suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    file_path = user_dir / stored_name
    file_path.write_bytes(file_bytes)

    # 保存提取的文本
    text_name = f"{uuid.uuid4().hex}.txt"
    text_path = user_dir / text_name
    text_path.write_text(extracted_text, encoding="utf-8")

    # 创建数据库记录
    document = DocumentItem(
        user_id=user_id,
        filename=filename,
        file_path=str(file_path),
        text_path=str(text_path),
        status=status,
        created_at=utc_now()
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)
    return document


async def list_documents(db: AsyncSession, user_id: int) -> list[DocumentItem]:
    """列出用户的所有文档"""
    result = await db.execute(
        select(DocumentItem)
        .where(DocumentItem.user_id == user_id)
        .order_by(DocumentItem.id.desc())
    )
    return list(result.scalars().all())


async def find_document_by_filename(db: AsyncSession, user_id: int, filename: str) -> DocumentItem | None:
    """根据文件名查找文档"""
    result = await db.execute(
        select(DocumentItem)
        .where(DocumentItem.user_id == user_id, DocumentItem.filename == filename)
    )
    return result.scalar_one_or_none()


async def delete_document(db: AsyncSession, user_id: int, filename: str) -> DocumentItem | None:
    """删除文档记录和文件"""
    document = await find_document_by_filename(db, user_id, filename)
    if not document:
        return None

    # 删除物理文件
    for path_str in (document.file_path, document.text_path):
        if not path_str:
            continue
        path = Path(path_str)
        if path.is_file():
            path.unlink()

    # 删除数据库记录
    await db.delete(document)
    await db.flush()

    return document
