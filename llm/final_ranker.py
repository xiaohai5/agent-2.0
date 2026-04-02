"""Final compression stage using lightweight MMR selection."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.documents import Document

try:
    from . import config_data as config
except ImportError:
    import config_data as config


class FinalCompressionRanker:
    def __init__(self, ranker_params: dict[str, Any] | None = None) -> None:
        self.params = config.get_splitter_params(ranker_params)
        self.lambda_mult = 0.7

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        normalized = re.sub(r"\s+", " ", text).strip().lower()
        if not normalized:
            return set()
        tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", normalized)
        expanded: set[str] = set()
        for token in tokens:
            expanded.add(token)
            if re.fullmatch(r"[\u4e00-\u9fff]+", token):
                expanded.update(token[idx : idx + 2] for idx in range(len(token) - 1))
                expanded.update(token)
        return expanded

    @staticmethod
    def _jaccard_similarity(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    def rank(self, query: str, docs: list[Document]) -> list[Document]:
        if not docs:
            return []

        query_tokens = self._tokenize(query)
        candidates: list[dict[str, Any]] = []
        for index, doc in enumerate(docs, start=1):
            metadata = doc.metadata if isinstance(doc.metadata, dict) else {}
            doc_tokens = self._tokenize(getattr(doc, "page_content", "") or "")
            base_score = float(metadata.get("_rerank_score", 0.0))
            if base_score == 0.0:
                base_score = 1.0 / index
            query_similarity = self._jaccard_similarity(query_tokens, doc_tokens)
            relevance = 0.8 * base_score + 0.2 * query_similarity
            candidates.append(
                {
                    "doc": doc,
                    "tokens": doc_tokens,
                    "relevance": relevance,
                }
            )

        selected: list[dict[str, Any]] = []
        remaining = candidates.copy()

        while remaining and len(selected) < self.params.top_k:
            best_item: dict[str, Any] | None = None
            best_score = float("-inf")
            for item in remaining:
                diversity_penalty = 0.0
                if selected:
                    diversity_penalty = max(
                        self._jaccard_similarity(item["tokens"], chosen["tokens"])
                        for chosen in selected
                    )
                mmr_score = self.lambda_mult * item["relevance"] - (1.0 - self.lambda_mult) * diversity_penalty
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_item = item

            if best_item is None:
                break
            selected.append(best_item)
            remaining.remove(best_item)

        final_docs: list[Document] = []
        for idx, item in enumerate(selected, start=1):
            doc = item["doc"]
            enriched = dict(doc.metadata if isinstance(doc.metadata, dict) else {})
            enriched["_final_rank"] = idx
            enriched["_final_ranker"] = "MMRTopKRanker"
            final_docs.append(Document(page_content=doc.page_content, metadata=enriched))
        return final_docs


LostInTheMiddleRanker = FinalCompressionRanker
