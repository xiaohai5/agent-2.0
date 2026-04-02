"""Compatibility layer for vector-store ingestion and deletion."""

from __future__ import annotations

import json
import uuid

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

try:
    from . import config_data as config
except ImportError:
    import config_data as config

try:
    from .chunking import chunk_documents
except ImportError:
    from chunking import chunk_documents


class KnowledgeBaseServce:
    """Backward-compatible knowledge base service used by the FastAPI routes."""

    def __init__(self, collection_name: str | None = None, splitter_params: dict | None = None) -> None:
        self.collection_name = collection_name or config.collection_name
        self.splitter_config = config.get_splitter_params(splitter_params)
        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=OpenAIEmbeddings(model=config.embedding_model),
            persist_directory="./chroma_db",
        )

    def ingest_documents(self, docs: list[Document]) -> str:
        if not docs:
            return "No documents to ingest."

        chunked_docs = chunk_documents(docs, self.splitter_config)
        if not chunked_docs:
            return "No document chunks generated."

        ids: list[str] = []
        for chunk in chunked_docs:
            metadata = self._sanitize_metadata(dict(chunk.metadata or {}))
            chunk_id = str(metadata.get("_doc_id") or uuid.uuid4())
            metadata["_doc_id"] = chunk_id
            metadata.setdefault("collection_name", self.collection_name)
            chunk.metadata = metadata
            ids.append(chunk_id)

        self.vector_store.add_documents(chunked_docs, ids=ids)

        file_count = len(
            {
                str((doc.metadata or {}).get("filename") or (doc.metadata or {}).get("source") or "")
                for doc in docs
            }
        )
        return f"Ingested {len(chunked_docs)} chunks from {file_count} file(s)."

    def upload_by_str(self, docs: list[Document]) -> str:
        return self.ingest_documents(docs)

    def delete_documents_by_filename(self, filename: str) -> int:
        payload = self.vector_store.get(where={"filename": filename}, include=["metadatas"])
        ids = payload.get("ids", []) if isinstance(payload, dict) else []
        if not ids:
            return 0

        self.vector_store.delete(ids=ids)
        return len(ids)

    def list_uploaded_filenames(self) -> list[str]:
        payload = self.vector_store.get(include=["metadatas"])
        metadatas = payload.get("metadatas", []) if isinstance(payload, dict) else []
        filenames: set[str] = set()
        for meta in metadatas:
            if not isinstance(meta, dict):
                continue
            name = meta.get("filename") or meta.get("source")
            if name:
                filenames.add(str(name))
        return sorted(filenames)

    @staticmethod
    def _sanitize_metadata(metadata: dict) -> dict:
        sanitized: dict = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    sanitized[key] = cleaned
                continue
            if isinstance(value, (bool, int, float)):
                sanitized[key] = value
                continue
            if isinstance(value, list):
                cleaned_list = []
                for item in value:
                    if item is None:
                        continue
                    if isinstance(item, (bool, int, float)):
                        cleaned_list.append(item)
                        continue
                    item_text = str(item).strip()
                    if item_text:
                        cleaned_list.append(item_text)
                if cleaned_list:
                    sanitized[key] = cleaned_list
                continue
            if isinstance(value, dict):
                if value:
                    sanitized[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
                continue

            value_text = str(value).strip()
            if value_text:
                sanitized[key] = value_text
        return sanitized


KnowledgeBaseService = KnowledgeBaseServce
