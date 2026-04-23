from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, status
from langchain_core.documents import Document
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.crued import vector_store as doc_crud
from backend.app.crued import graphrag as graph_crud
from backend.app.services.graphrag_service import graphrag_demo_service


SUPPORTED_EXTENSIONS = {
    ".txt",
    ".tx",
    ".md",
    ".markdown",
    ".json",
    ".jsonl",
    ".csv",
    ".xls",
    ".xlsx",
    ".html",
    ".htm",
    ".pdf",
    ".docx",
    ".pptx",
}


def get_user_collection_name(user_id: int) -> str:
    return f"user_{user_id}_kb"


@lru_cache(maxsize=256)
def _get_kb_service(collection_name: str):
    from llm.knowledge_base import KnowledgeBaseServce
    from llm.llm import read_llm

    read_llm()
    return KnowledgeBaseServce(collection_name=collection_name)


class _MemoryUploadFile:
    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


def _validate_supported_file(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported document type. Supported extensions: {supported}",
        )


def _parse_documents(filename: str, file_bytes: bytes) -> list[Document]:
    _validate_supported_file(filename)
    try:
        from llm.load import load_file_to_document

        return load_file_to_document(_MemoryUploadFile(filename, file_bytes))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document parse failed: {exc}",
        ) from exc


class DocumentService:
    async def upload(self, db: AsyncSession, user_id: int, filename: str, file_bytes: bytes) -> dict:
        docs = _parse_documents(filename, file_bytes)
        if not docs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document parse failed: empty document",
            )

        for doc in docs:
            doc.metadata = dict(doc.metadata or {})
            doc.metadata["filename"] = filename
            doc.metadata["user_id"] = user_id

        try:
            kb_message, graph_payload = await asyncio.gather(
                asyncio.to_thread(
                    _get_kb_service(get_user_collection_name(user_id)).ingest_documents,
                    docs,
                ),
                graphrag_demo_service.build_graph_payload(docs),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document ingest failed: {exc}",
            ) from exc

        record = await doc_crud.save_document(
            db=db,
            user_id=user_id,
            filename=filename,
            file_bytes=file_bytes,
            extracted_text="\n\n".join(doc.page_content for doc in docs if doc.page_content),
            status="indexed",
        )
        graph_stats = await graphrag_demo_service.ingest_payload(
            db,
            user_id=user_id,
            document_id=record.id,
            filename=filename,
            payload=graph_payload,
        )
        await db.commit()

        return {
            "filename": record.filename,
            "status": record.status,
            "message": kb_message,
            "graph": {
                "semantic_chunks": graph_stats.semantic_chunks,
                "entities": graph_stats.entities,
                "relationships": graph_stats.relationships,
            },
        }

    async def list_documents(self, db: AsyncSession, user_id: int) -> list[dict]:
        documents = await doc_crud.list_documents(db, user_id)
        return [
            {"id": doc.id, "filename": doc.filename, "status": doc.status}
            for doc in documents
        ]

    async def delete(self, db: AsyncSession, user_id: int, filename: str) -> dict:
        try:
            deleted_chunks = _get_kb_service(get_user_collection_name(user_id)).delete_documents_by_filename(filename)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Vector store delete failed: {exc}",
            ) from exc

        existing_record = await doc_crud.find_document_by_filename(db, user_id=user_id, filename=filename)
        if existing_record:
            await graph_crud.delete_document_graph(db, user_id=user_id, document_id=existing_record.id)

        record = await doc_crud.delete_document(db, user_id=user_id, filename=filename)
        if not record and deleted_chunks == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        await db.commit()
        return {"filename": filename, "message": "Document deleted successfully."}

    async def graph_summary(self, db: AsyncSession, user_id: int, filename: str | None = None) -> dict:
        return await graphrag_demo_service.get_summary(db, user_id=user_id, filename=filename)


document_service = DocumentService()
