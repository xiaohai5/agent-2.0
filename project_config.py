"""Global project settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _parse_bool(value: str | bool | None, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ProjectSettings:
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    docling_tokenizer: str = os.getenv("DOCLING_TOKENIZER", "BAAI/bge-m3")
    vector_collection: str = os.getenv("VECTOR_COLLECTION", "knowledge_base")
    md5_path: str = os.getenv("MD5_PATH", "./md5.txt")
    max_token_limit: int = int(os.getenv("MAX_TOKEN_LIMIT", "10"))
    retrieval_profile: str = os.getenv("RETRIEVAL_PROFILE", "online").strip().lower()
    api_base_url: str = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api")
    async_database_url: str = os.getenv(
        "ASYNC_DATABASE_URL",
        "mysql+aiomysql://root:123456@localhost:3306/agent?charset=utf8mb4",
    )
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "500"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "50"))
    table_row_batch_size: int = int(os.getenv("TABLE_ROW_BATCH_SIZE", "5"))
    table_row_overlap: int = int(os.getenv("TABLE_ROW_OVERLAP", "1"))
    final_top_k: int = int(os.getenv("TOP_K", "5"))
    max_split_num: int = int(os.getenv("MAX_SPLITE_NUM", "100"))
    request_timeout_seconds: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
    chat_timeout_seconds: int = int(os.getenv("CHAT_TIMEOUT_SECONDS", "300"))
    upload_timeout_seconds: int = int(os.getenv("UPLOAD_TIMEOUT_SECONDS", "1800"))
    online_use_query_rewrite: bool = _parse_bool(os.getenv("USE_QUERY_REWRITE"), False)
    online_final_rank_enabled: bool = _parse_bool(os.getenv("FINAL_RANK_ENABLED"), True)
    online_vector_query_count: int = int(os.getenv("VECTOR_QUERY_COUNT", "1"))
    online_keyword_query_count: int = int(os.getenv("KEYWORD_QUERY_COUNT", "1"))
    online_vector_top_k: int = int(os.getenv("VECTOR_TOP_K", "10"))
    online_bm25_top_k: int = int(os.getenv("BM25_TOP_K", "10"))
    online_max_candidates: int = int(os.getenv("MAX_CANDIDATES", "20"))
    online_rerank_top_k: int = int(os.getenv("RERANK_TOP_K", "10"))
    online_rerank_enabled: bool = _parse_bool(os.getenv("RERANK_ENABLED"), True)
    benchmark_use_query_rewrite: bool = _parse_bool(os.getenv("USE_QUERY_REWRITE"), False)
    benchmark_final_rank_enabled: bool = _parse_bool(os.getenv("FINAL_RANK_ENABLED"), False)
    benchmark_vector_query_count: int = int(os.getenv("VECTOR_QUERY_COUNT", "1"))
    benchmark_keyword_query_count: int = int(os.getenv("KEYWORD_QUERY_COUNT", "1"))
    benchmark_vector_top_k: int = int(os.getenv("VECTOR_TOP_K", "10"))
    benchmark_bm25_top_k: int = int(os.getenv("BM25_TOP_K", "10"))
    benchmark_max_candidates: int = int(os.getenv("MAX_CANDIDATES", "20"))
    benchmark_rerank_top_k: int = int(os.getenv("RERANK_TOP_K", "10"))
    benchmark_rerank_enabled: bool = _parse_bool(os.getenv("RERANK_ENABLED"), True)
    rerank_model_name: str = os.getenv("RERANK_MODEL_NAME", "BAAI/bge-reranker-v2-m3")
    rerank_device: str = os.getenv("RERANK_DEVICE", "cuda:0")
    rerank_use_fp16: bool = _parse_bool(os.getenv("RERANK_USE_FP16"), True)
    rerank_normalize: bool = _parse_bool(os.getenv("RERANK_NORMALIZE"), True)


SETTINGS = ProjectSettings()
