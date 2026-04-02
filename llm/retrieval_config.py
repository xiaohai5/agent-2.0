from dataclasses import dataclass
from typing import Any


@dataclass
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

    def get_config(self) -> tuple[bool, bool, int, int, int, int, int, int]:
        return (
            self.use_query_rewrite,
            self.final_rank_enabled,
            self.vector_query_count,
            self.keyword_query_count,
            self.vector_top_k,
            self.bm25_top_k,
            self.max_candidates,
            self.rerank_top_k,
        )
