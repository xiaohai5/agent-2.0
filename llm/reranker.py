"""Second-layer reranker service using lightweight reciprocal rank fusion."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from langchain_core.documents import Document

try:
    from . import config_data as config
except ImportError:
    import config_data as config


class QueryReranker:
    def __init__(self, rerank_params: dict[str, Any] | None = None) -> None:
        self.params = config.get_rerank_params(rerank_params)
        self.rrf_k = 60.0
        self.multi_hit_bonus = 0.002
        self.source_weights = {
            "vector": 0.3,
            "bm25": 0.7,
        }

    def _aggregate_docs(self, docs: list[Document]) -> list[Document]:
        aggregated: dict[str, dict[str, Any]] = {}
        order: list[str] = []

        for doc in docs:
            metadata = doc.metadata if isinstance(doc.metadata, dict) else {}
            key = str(metadata.get("_doc_id") or metadata.get("id") or doc.page_content)
            hits = metadata.get("_recall_hits", [])
            if not isinstance(hits, list) or not hits:
                hits = [
                    {
                        "type": str(metadata.get("_recall_type", "")),
                        "query": str(metadata.get("_recall_query", "")),
                        "rank": int(metadata.get("_recall_rank", 10**9)),
                    }
                ]

            if key not in aggregated:
                aggregated[key] = {
                    "doc": doc,
                    "hits": [],
                }
                order.append(key)

            aggregated[key]["hits"].extend(hits)

        merged_docs: list[Document] = []
        for key in order:
            entry = aggregated[key]
            doc = entry["doc"]
            enriched = dict(doc.metadata if isinstance(doc.metadata, dict) else {})
            enriched["_recall_hits"] = entry["hits"]
            merged_docs.append(Document(page_content=doc.page_content, metadata=enriched))
        return merged_docs

    def _collect_rrf_scores(self, docs: list[Document]) -> dict[str, float]:
        scores: dict[str, float] = defaultdict(float)
        for doc in docs:
            metadata = doc.metadata if isinstance(doc.metadata, dict) else {}
            key = str(metadata.get("_doc_id") or metadata.get("id") or doc.page_content)
            hits = metadata.get("_recall_hits", [])
            hit_types: set[str] = set()
            for hit in hits:
                if not isinstance(hit, dict):
                    continue
                rank = int(hit.get("rank", 10**9))
                if rank >= 10**9:
                    continue
                hit_type = str(hit.get("type", "")).strip()
                if hit_type:
                    hit_types.add(hit_type)
                weight = float(self.source_weights.get(hit_type, 0.0))
                scores[key] += weight / (self.rrf_k + rank)
            if "vector" in hit_types and "bm25" in hit_types:
                scores[key] += self.multi_hit_bonus
        return scores

    def rerank(self, query: str, docs: list[Document]) -> list[Document]:
        if not docs:
            return []

        if not self.params.enabled:
            return docs[: self.params.top_k]

        docs = self._aggregate_docs(docs)
        scored_docs: list[tuple[float, Document]] = []
        scores = self._collect_rrf_scores(docs)
        for doc in docs:
            metadata = doc.metadata if isinstance(doc.metadata, dict) else {}
            key = str(metadata.get("_doc_id") or metadata.get("id") or doc.page_content)
            score = float(scores.get(key, 0.0))
            enriched = dict(doc.metadata)
            enriched["_rerank_score"] = score
            enriched["_rerank_skipped"] = False
            enriched["_rerank_strategy"] = "rrf"
            scored_docs.append((float(score), Document(page_content=doc.page_content, metadata=enriched)))

        scored_docs.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored_docs[: self.params.top_k]]
