"""Project-level LLM config and splitter params."""

from __future__ import annotations

from typing import Any

from project_config import SETTINGS

try:
    from .splitter_config import SplitterConfig
except ImportError:
    from splitter_config import SplitterConfig

try:
    from .retrieval_config import RetrievalConfig
except ImportError:
    from retrieval_config import RetrievalConfig

try:
    from .rerank_config import RerankConfig
except ImportError:
    from rerank_config import RerankConfig


llm_model = SETTINGS.llm_model
embedding_model = SETTINGS.embedding_model
docling_tokenizer = SETTINGS.docling_tokenizer
collection_name = SETTINGS.vector_collection
md5_path = SETTINGS.md5_path
separators = None
max_token_limit = SETTINGS.max_token_limit
retrieval_profile = SETTINGS.retrieval_profile

_DEFAULT_SPLITTER = SplitterConfig(
    chunk_size=SETTINGS.chunk_size,
    chunk_overlap=SETTINGS.chunk_overlap,
    table_row_batch_size=SETTINGS.table_row_batch_size,
    table_row_overlap=SETTINGS.table_row_overlap,
    top_k=SETTINGS.final_top_k,
)

_PROFILE_RETRIEVAL_DEFAULTS: dict[str, dict[str, Any]] = {
    "online": {
        "use_query_rewrite": SETTINGS.online_use_query_rewrite,
        "final_rank_enabled": SETTINGS.online_final_rank_enabled,
        "vector_query_count": SETTINGS.online_vector_query_count,
        "keyword_query_count": SETTINGS.online_keyword_query_count,
        "vector_top_k": SETTINGS.online_vector_top_k,
        "bm25_top_k": SETTINGS.online_bm25_top_k,
        "max_candidates": SETTINGS.online_max_candidates,
        "rerank_top_k": SETTINGS.online_rerank_top_k,
    },
    "benchmark": {
        "use_query_rewrite": SETTINGS.benchmark_use_query_rewrite,
        "final_rank_enabled": SETTINGS.benchmark_final_rank_enabled,
        "vector_query_count": SETTINGS.benchmark_vector_query_count,
        "keyword_query_count": SETTINGS.benchmark_keyword_query_count,
        "vector_top_k": SETTINGS.benchmark_vector_top_k,
        "bm25_top_k": SETTINGS.benchmark_bm25_top_k,
        "max_candidates": SETTINGS.benchmark_max_candidates,
        "rerank_top_k": SETTINGS.benchmark_rerank_top_k,
    },
}

_PROFILE_RERANK_DEFAULTS: dict[str, dict[str, Any]] = {
    "online": {
        "rerank_enabled": SETTINGS.online_rerank_enabled,
        "rerank_top_k": SETTINGS.online_rerank_top_k,
        "rerank_model_name": SETTINGS.rerank_model_name,
        "rerank_device": SETTINGS.rerank_device,
        "rerank_use_fp16": SETTINGS.rerank_use_fp16,
        "rerank_normalize": SETTINGS.rerank_normalize,
    },
    "benchmark": {
        "rerank_enabled": SETTINGS.benchmark_rerank_enabled,
        "rerank_top_k": SETTINGS.benchmark_rerank_top_k,
        "rerank_model_name": SETTINGS.rerank_model_name,
        "rerank_device": SETTINGS.rerank_device,
        "rerank_use_fp16": SETTINGS.rerank_use_fp16,
        "rerank_normalize": SETTINGS.rerank_normalize,
    },
}

_SPLITTER_FIELDS = ("chunk_size", "chunk_overlap", "table_row_batch_size", "table_row_overlap", "top_k")
_RETRIEVAL_FIELDS = (
    "use_query_rewrite",
    "final_rank_enabled",
    "vector_query_count",
    "keyword_query_count",
    "vector_top_k",
    "bm25_top_k",
    "max_candidates",
    "rerank_top_k",
)
_RERANK_FIELDS = (
    "rerank_enabled",
    "rerank_top_k",
    "rerank_model_name",
    "rerank_device",
    "rerank_use_fp16",
    "rerank_normalize",
)
_RERANK_FALLBACK_KEYS = {
    "rerank_top_k": ("top_k",),
}


def _resolve_profile(overrides: dict[str, Any] | None = None) -> str:
    candidate = str((overrides or {}).get("retrieval_profile", retrieval_profile)).strip().lower()
    if candidate in _PROFILE_RETRIEVAL_DEFAULTS:
        return candidate
    return "online"


def _merge_defaults(
    overrides: dict[str, Any] | None,
    defaults: dict[str, Any],
    fields: tuple[str, ...],
    fallback_keys: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    if not overrides:
        return defaults.copy()

    merged: dict[str, Any] = {}
    for field in fields:
        value = overrides.get(field)
        if value is None and fallback_keys:
            for fallback_key in fallback_keys.get(field, ()):
                value = overrides.get(fallback_key)
                if value is not None:
                    break
        merged[field] = defaults[field] if value is None else value
    return merged


_DEFAULT_RETRIEVAL = RetrievalConfig.from_mapping(_PROFILE_RETRIEVAL_DEFAULTS[_resolve_profile()])
_DEFAULT_RERANK = RerankConfig.from_mapping(_PROFILE_RERANK_DEFAULTS[_resolve_profile()])


def get_splitter_params(overrides: dict[str, Any] | None = None) -> SplitterConfig:
    """Return effective splitter params with optional runtime overrides."""
    if not overrides:
        return _DEFAULT_SPLITTER
    merged = _merge_defaults(
        overrides,
        {
            "chunk_size": _DEFAULT_SPLITTER.chunk_size,
            "chunk_overlap": _DEFAULT_SPLITTER.chunk_overlap,
            "table_row_batch_size": _DEFAULT_SPLITTER.table_row_batch_size,
            "table_row_overlap": _DEFAULT_SPLITTER.table_row_overlap,
            "top_k": _DEFAULT_SPLITTER.top_k,
        },
        _SPLITTER_FIELDS,
    )
    return SplitterConfig.from_mapping(merged)


def get_retrieval_params(overrides: dict[str, Any] | None = None) -> RetrievalConfig:
    """Return effective first-layer retrieval params with optional runtime overrides."""
    if not overrides:
        return _DEFAULT_RETRIEVAL
    profile = _resolve_profile(overrides)
    merged = _merge_defaults(overrides, _PROFILE_RETRIEVAL_DEFAULTS[profile], _RETRIEVAL_FIELDS)
    return RetrievalConfig.from_mapping(merged)


def get_rerank_params(overrides: dict[str, Any] | None = None) -> RerankConfig:
    """Return effective rerank params with optional runtime overrides."""
    if not overrides:
        return _DEFAULT_RERANK
    profile = _resolve_profile(overrides)
    merged = _merge_defaults(
        overrides,
        _PROFILE_RERANK_DEFAULTS[profile],
        _RERANK_FIELDS,
        fallback_keys=_RERANK_FALLBACK_KEYS,
    )
    return RerankConfig.from_mapping(merged)


chunk_size = _DEFAULT_SPLITTER.chunk_size
chunk_overlap = _DEFAULT_SPLITTER.chunk_overlap
table_row_batch_size = _DEFAULT_SPLITTER.table_row_batch_size
table_row_overlap = _DEFAULT_SPLITTER.table_row_overlap
top_k = _DEFAULT_SPLITTER.top_k
