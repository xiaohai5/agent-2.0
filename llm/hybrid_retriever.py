"""Hybrid retrieval with first-layer recall and second-layer rerank."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_community.retrievers import BM25Retriever
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

try:
    import project_config as config
except ImportError:
    import project_config as config

try:
    from .reranker import QueryReranker
except ImportError:
    from reranker import QueryReranker

try:
    from .final_ranker import FinalCompressionRanker
except ImportError:
    from final_ranker import FinalCompressionRanker

class FirstLayerHybridRetriever:
    def __init__(self, splitter_params: dict[str, Any] | None = None, collection_name: str | None = None) -> None:
        self.retrieval_params = config.get_retrieval_params(splitter_params)
        self.collection_name = collection_name or config.collection_name
        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=OpenAIEmbeddings(model=config.embedding_model),
            persist_directory=config.SETTINGS.chroma_persist_directory,
        )
        self.query_llm = (
            ChatOpenAI(model=config.llm_model, temperature=0)
            if self.retrieval_params.use_query_rewrite
            else None
        )
        self._documents = self._load_documents()
        self.bm25 = (
            BM25Retriever.from_documents(self._documents, preprocess_func=self._bm25_preprocess)
            if self._documents
            else None
        )
        if self.bm25 is not None:
            self.bm25.k = self.retrieval_params.bm25_top_k
        self.reranker = QueryReranker(splitter_params)
        self.final_ranker = FinalCompressionRanker(splitter_params)

    @staticmethod
    def _bm25_preprocess(text: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", text).strip().lower()
        if not normalized:
            return []

        tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", normalized)
        expanded: list[str] = []
        for token in tokens:
            expanded.append(token)
            if re.fullmatch(r"[\u4e00-\u9fff]+", token):
                expanded.extend(list(token))
                if len(token) > 1:
                    expanded.extend(token[idx:idx + 2] for idx in range(len(token) - 1))
        return expanded

    def _load_documents(self) -> list[Document]:
        payload = self.vector_store.get(include=["documents", "metadatas"])
        documents = payload.get("documents", []) if isinstance(payload, dict) else []
        metadatas = payload.get("metadatas", []) if isinstance(payload, dict) else []
        ids = payload.get("ids", []) if isinstance(payload, dict) else []

        loaded_docs: list[Document] = []
        for idx, content in enumerate(documents):
            if not content:
                continue
            metadata = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
            doc_id = ids[idx] if idx < len(ids) else str(idx)
            merged_metadata = dict(metadata)
            merged_metadata.setdefault("_doc_id", str(doc_id))
            loaded_docs.append(Document(page_content=content, metadata=merged_metadata))
        return loaded_docs

    def _build_rewrite_prompt(self, query: str) -> str:
        return (
            "你是 RAG 检索改写助手。\n"
            "请基于用户问题返回一个 JSON 对象，必须包含两个字段：\n"
            f'1. "vector_queries": {self.retrieval_params.vector_query_count} 条适合语义向量检索的改写问句。\n'
            f'2. "keyword_queries": {self.retrieval_params.keyword_query_count} 条适合 BM25/关键词检索的查询句。\n'
            "要求：\n"
            "1. 保持原始问题的真实意图不变。\n"
            "2. vector_queries 更自然完整，适合语义理解。\n"
            "3. keyword_queries 突出实体、术语、缩写、时间、数字和约束条件。\n"
            "4. 使用中文输出。\n"
            "5. 只返回 JSON，不要补充解释。\n"
            f"原始问题：{query}"
        )

    def _normalize_queries(self, queries: list[str], expected_count: int, original_query: str) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()

        for item in queries:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            cleaned.append(text)

        if original_query not in seen:
            cleaned.insert(0, original_query)
            seen.add(original_query)

        while len(cleaned) < expected_count:
            fallback = f"{original_query} {len(cleaned) + 1}"
            if fallback in seen:
                break
            cleaned.append(fallback)
            seen.add(fallback)

        return cleaned[:expected_count]

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("No JSON object found in rewrite response.")
        return json.loads(text[start : end + 1])

    def _rewrite_queries(self, query: str) -> tuple[list[str], list[str]]:
        expected_vector = self.retrieval_params.vector_query_count
        expected_keyword = self.retrieval_params.keyword_query_count
        fallback_vector = self._normalize_queries([], expected_vector, query)
        fallback_keyword = self._normalize_queries([], expected_keyword, query)

        if not self.retrieval_params.use_query_rewrite or self.query_llm is None:
            return fallback_vector, fallback_keyword

        try:
            response = self.query_llm.invoke(self._build_rewrite_prompt(query))
            content = response.content if hasattr(response, "content") else str(response)
            parsed = self._extract_json(content)
        except Exception:
            return fallback_vector, fallback_keyword

        vector_queries = parsed.get("vector_queries", []) if isinstance(parsed, dict) else []
        keyword_queries = parsed.get("keyword_queries", []) if isinstance(parsed, dict) else []
        return (
            self._normalize_queries(vector_queries, expected_vector, query),
            self._normalize_queries(keyword_queries, expected_keyword, query),
        )

    def _vector_search(self, queries: list[str]) -> list[Document]:
        docs: list[Document] = []
        for rewritten_query in queries:
            results = self.vector_store.similarity_search(
                rewritten_query,
                k=self.retrieval_params.vector_top_k,
            )
            for rank, doc in enumerate(results, start=1):
                enriched = dict(doc.metadata)
                enriched["_recall_query"] = rewritten_query
                enriched["_recall_type"] = "vector"
                enriched["_recall_rank"] = rank
                docs.append(Document(page_content=doc.page_content, metadata=enriched))
        return docs

    def _bm25_search(self, queries: list[str]) -> list[Document]:
        if self.bm25 is None:
            return []

        docs: list[Document] = []
        for rewritten_query in queries:
            results = self.bm25.invoke(rewritten_query)
            for rank, doc in enumerate(results, start=1):
                enriched = dict(doc.metadata)
                enriched["_recall_query"] = rewritten_query
                enriched["_recall_type"] = "bm25"
                enriched["_recall_rank"] = rank
                docs.append(Document(page_content=doc.page_content, metadata=enriched))
        return docs

    def _limit_candidates(self, docs: list[Document]) -> list[Document]:
        return docs[: self.retrieval_params.max_candidates]

    def invoke(self, query: str) -> list[Document]:
        if not self._documents:
            return []

        vector_queries, keyword_queries = self._rewrite_queries(query)
        recalled_docs = self._vector_search(vector_queries)
        recalled_docs.extend(self._bm25_search(keyword_queries))
        first_layer_docs = self._limit_candidates(recalled_docs)
        reranked_docs = self.reranker.rerank(query, first_layer_docs)
        if not self.retrieval_params.final_rank_enabled:
            return reranked_docs[: self.retrieval_params.rerank_top_k]
        return self.final_ranker.rank(query, reranked_docs)
