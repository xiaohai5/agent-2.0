"""Single source of truth for all runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv


load_dotenv()


def _split_env_args(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        return default
    args = tuple(item.strip() for item in value.split(",") if item.strip())
    return args or default


def _resolve_amap_mcp_url() -> str:
    url = os.getenv("AMAP_MCP_URL", "").strip()
    if url:
        return url

    key = os.getenv("AMAP_MCP_KEY", "").strip()
    if key:
        return f"https://mcp.amap.com/mcp?key={key}"

    return "https://mcp.amap.com/mcp?key=your-amap-key"


def _parse_bool(value: str | bool | None, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SplitterConfig:
    chunk_size: int = 500
    chunk_overlap: int = 50
    table_row_batch_size: int = 5
    table_row_overlap: int = 1
    top_k: int = 5

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "SplitterConfig":
        if not data:
            return cls()
        return cls(
            chunk_size=int(data.get("chunk_size", cls.chunk_size)),
            chunk_overlap=int(data.get("chunk_overlap", cls.chunk_overlap)),
            table_row_batch_size=int(data.get("table_row_batch_size", cls.table_row_batch_size)),
            table_row_overlap=int(data.get("table_row_overlap", cls.table_row_overlap)),
            top_k=int(data.get("top_k", cls.top_k)),
        )


@dataclass(frozen=True)
class RetrievalConfig:
    use_query_rewrite: bool = False
    final_rank_enabled: bool = True
    vector_query_count: int = 1
    keyword_query_count: int = 1
    vector_top_k: int = 10
    bm25_top_k: int = 10
    max_candidates: int = 20
    rerank_top_k: int = 10

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "RetrievalConfig":
        if not data:
            return cls()
        return cls(
            use_query_rewrite=bool(data.get("use_query_rewrite", cls.use_query_rewrite)),
            final_rank_enabled=bool(data.get("final_rank_enabled", cls.final_rank_enabled)),
            vector_query_count=int(data.get("vector_query_count", cls.vector_query_count)),
            keyword_query_count=int(data.get("keyword_query_count", cls.keyword_query_count)),
            vector_top_k=int(data.get("vector_top_k", cls.vector_top_k)),
            bm25_top_k=int(data.get("bm25_top_k", cls.bm25_top_k)),
            max_candidates=int(data.get("max_candidates", cls.max_candidates)),
            rerank_top_k=int(data.get("rerank_top_k", cls.rerank_top_k)),
        )


@dataclass(frozen=True)
class RerankConfig:
    enabled: bool = True
    top_k: int = 10
    model_name: str = "BAAI/bge-reranker-v2-m3"
    device: str = "cuda:0"
    use_fp16: bool = True
    normalize: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "RerankConfig":
        if not data:
            return cls()
        return cls(
            enabled=bool(data.get("rerank_enabled", data.get("enabled", cls.enabled))),
            top_k=int(data.get("rerank_top_k", data.get("top_k", cls.top_k))),
            model_name=str(data.get("rerank_model_name", cls.model_name)),
            device=str(data.get("rerank_device", data.get("device", cls.device))),
            use_fp16=bool(data.get("rerank_use_fp16", cls.use_fp16)),
            normalize=bool(data.get("rerank_normalize", cls.normalize)),
        )


@dataclass(frozen=True)
class ProjectSettings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    langsmith_tracing: bool = False
    langsmith_endpoint: str = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")
    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "agent-2.0")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    docling_tokenizer: str = "BAAI/bge-m3"
    docling_export_type: str = "markdown"
    vector_collection: str = "knowledge_base"
    chroma_persist_directory: str = os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db")
    md5_path: str = os.getenv("MD5_PATH", "./md5.txt")
    max_token_limit: int = 10
    retrieval_profile: str = "online"
    async_database_url: str = os.getenv(
        "ASYNC_DATABASE_URL",
        "mysql+aiomysql://root:password@localhost:3306/agent?charset=utf8mb4",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    short_memory_ttl_seconds: int = int(os.getenv("SHORT_MEMORY_TTL_SECONDS", "604800"))
    chunk_size: int = 500
    chunk_overlap: int = 50
    table_row_batch_size: int = 5
    table_row_overlap: int = 1
    final_top_k: int = 5
    max_split_num: int = 100
    request_timeout_seconds: int = 30
    chat_timeout_seconds: int = 300
    upload_timeout_seconds: int = 1800
    online_use_query_rewrite: bool = False
    online_final_rank_enabled: bool = True
    online_vector_query_count: int = 1
    online_keyword_query_count: int = 1
    online_vector_top_k: int = 10
    online_bm25_top_k: int = 10
    online_max_candidates: int = 20
    online_rerank_top_k: int = 10
    online_rerank_enabled: bool = True
    benchmark_use_query_rewrite: bool = False
    benchmark_final_rank_enabled: bool = False
    benchmark_vector_query_count: int = 1
    benchmark_keyword_query_count: int = 1
    benchmark_vector_top_k: int = 10
    benchmark_bm25_top_k: int = 10
    benchmark_max_candidates: int = 20
    benchmark_rerank_top_k: int = 10
    benchmark_rerank_enabled: bool = True
    rerank_model_name: str = "BAAI/bge-reranker-v2-m3"
    rerank_device: str = "cuda:0"
    rerank_use_fp16: bool = True
    rerank_normalize: bool = True
    amap_mcp_url: str = _resolve_amap_mcp_url()
    ticket_mcp_command: str = os.getenv("TICKET_MCP_COMMAND", "npx")
    ticket_mcp_args: tuple[str, ...] = _split_env_args(os.getenv("TICKET_MCP_ARGS"), ("-y", "12306-mcp"))
    http_proxy: str = ""
    https_proxy: str = ""
    all_proxy: str = ""
    no_proxy: str = ""


SETTINGS = ProjectSettings()

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


def apply_runtime_environment() -> None:
    if not SETTINGS.openai_api_key:
        raise RuntimeError("Missing OpenAI API key in project_config.py")

    proxy_map = {
        "HTTP_PROXY": SETTINGS.http_proxy,
        "HTTPS_PROXY": SETTINGS.https_proxy,
        "ALL_PROXY": SETTINGS.all_proxy,
        "NO_PROXY": SETTINGS.no_proxy,
    }
    for key, value in proxy_map.items():
        if value:
            os.environ[key] = value
            os.environ[key.lower()] = value
        else:
            os.environ.pop(key, None)
            os.environ.pop(key.lower(), None)

    os.environ["OPENAI_API_KEY"] = SETTINGS.openai_api_key
    os.environ["OPENAI_BASE_URL"] = SETTINGS.openai_base_url.rstrip("/")
    if SETTINGS.tavily_api_key:
        os.environ["TAVILY_API_KEY"] = SETTINGS.tavily_api_key
    else:
        os.environ.pop("TAVILY_API_KEY", None)

    if SETTINGS.langsmith_tracing:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGSMITH_ENDPOINT"] = SETTINGS.langsmith_endpoint
        os.environ["LANGSMITH_API_KEY"] = SETTINGS.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = SETTINGS.langsmith_project
    else:
        for key in (
            "LANGSMITH_TRACING",
            "LANGCHAIN_TRACING_V2",
            "LANGCHAIN_TRACING",
            "LANGSMITH_ENDPOINT",
            "LANGSMITH_API_KEY",
            "LANGSMITH_PROJECT",
        ):
            os.environ.pop(key, None)


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
    if not overrides:
        return _DEFAULT_RETRIEVAL
    profile = _resolve_profile(overrides)
    merged = _merge_defaults(overrides, _PROFILE_RETRIEVAL_DEFAULTS[profile], _RETRIEVAL_FIELDS)
    return RetrievalConfig.from_mapping(merged)


def get_rerank_params(overrides: dict[str, Any] | None = None) -> RerankConfig:
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
