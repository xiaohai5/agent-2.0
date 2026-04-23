from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.crued import graphrag as graph_crud
from llm.llm import read_llm
from project_config import SETTINGS


MAX_SOURCE_TEXT_CHARS = 12000
MAX_SEMANTIC_CHUNK_CHARS = 1800


class GraphRAGDemoService:
    def __init__(self) -> None:
        self._llm: ChatOpenAI | None = None

    def _get_llm(self) -> ChatOpenAI:
        if self._llm is None:
            read_llm()
            self._llm = ChatOpenAI(model=SETTINGS.llm_model, temperature=0)
        return self._llm

    async def build_graph_payload(self, docs: list[Document]) -> dict[str, list[dict[str, Any]]]:
        source_text = self._render_source_text(docs)
        if not source_text:
            return {"chunks": [], "entities": [], "relationships": []}

        try:
            chunks = await self._llm_build_semantic_chunks(source_text)
            entities, relationships = await self._llm_extract_graph(chunks)
        except Exception:
            chunks = self._rule_build_semantic_chunks(docs)
            entities, relationships = self._rule_extract_graph(chunks)

        chunks = self._normalize_chunks(chunks)
        entities = self._normalize_entities(entities, len(chunks))
        relationships = self._normalize_relationships(relationships, len(chunks))
        return {
            "chunks": chunks,
            "entities": entities,
            "relationships": relationships,
        }

    async def ingest_documents(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        document_id: int,
        filename: str,
        docs: list[Document],
    ) -> graph_crud.GraphIngestStats:
        payload = await self.build_graph_payload(docs)
        return await self.ingest_payload(
            db,
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            payload=payload,
        )

    async def ingest_payload(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        document_id: int,
        filename: str,
        payload: dict[str, list[dict[str, Any]]],
    ) -> graph_crud.GraphIngestStats:
        return await graph_crud.replace_document_graph(
            db,
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            chunks=payload.get("chunks", []),
            entities=payload.get("entities", []),
            relationships=payload.get("relationships", []),
        )

    async def get_summary(self, db: AsyncSession, *, user_id: int, filename: str | None = None) -> dict[str, Any]:
        return await graph_crud.get_document_graph_summary(db, user_id=user_id, filename=filename)

    async def _llm_build_semantic_chunks(self, source_text: str) -> list[dict[str, Any]]:
        prompt = (
            "你是 GraphRAG 语义分块器。请把文档切成语义完整块，不要按固定长度硬切。\n"
            "要求：\n"
            "1. 每个块表达一个完整主题、步骤、表格含义或段落组。\n"
            f"2. 单块尽量不超过 {MAX_SEMANTIC_CHUNK_CHARS} 个字符，必要时可稍微超过以保持语义完整。\n"
            "3. 保留原文事实，不要总结改写。\n"
            "4. 只输出 JSON，格式为：{\"chunks\":[{\"title\":\"...\",\"content\":\"...\"}]}。\n\n"
            f"文档：\n{source_text[:MAX_SOURCE_TEXT_CHARS]}"
        )
        response = await self._get_llm().ainvoke([{"role": "user", "content": prompt}])
        payload = self._extract_json_object(str(getattr(response, "content", response)))
        chunks = payload.get("chunks", []) if isinstance(payload, dict) else []
        if not isinstance(chunks, list) or not chunks:
            raise ValueError("LLM semantic chunking returned no chunks.")
        return [
            {
                "chunk_index": index,
                "title": str(item.get("title") or "")[:255] if isinstance(item, dict) else "",
                "content": str(item.get("content") or "").strip() if isinstance(item, dict) else "",
            }
            for index, item in enumerate(chunks)
        ]

    async def _llm_extract_graph(self, chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        all_entities: list[dict[str, Any]] = []
        all_relationships: list[dict[str, Any]] = []

        for chunk in chunks:
            chunk_index = int(chunk.get("chunk_index", 0))
            content = str(chunk.get("content") or "")
            if not content.strip():
                continue
            prompt = (
                "你是 GraphRAG 实体关系抽取器。请从语义块中抽取实体和关系。\n"
                "实体类型建议使用：person, organization, location, product, event, technical_concept, concept, other。\n"
                "关系类型使用英文蛇形命名，例如 related_to, part_of, depends_on, uses, located_in, created_by。\n"
                "只输出 JSON，格式为：\n"
                "{\"entities\":[{\"name\":\"...\",\"entity_type\":\"...\",\"description\":\"...\"}],"
                "\"relationships\":[{\"source_entity\":\"...\",\"target_entity\":\"...\",\"relation_type\":\"...\",\"evidence\":\"...\"}]}\n\n"
                f"语义块标题：{chunk.get('title') or ''}\n"
                f"语义块内容：\n{content[:MAX_SEMANTIC_CHUNK_CHARS * 2]}"
            )
            response = await self._get_llm().ainvoke([{"role": "user", "content": prompt}])
            payload = self._extract_json_object(str(getattr(response, "content", response)))
            entities = payload.get("entities", []) if isinstance(payload, dict) else []
            relationships = payload.get("relationships", []) if isinstance(payload, dict) else []

            if isinstance(entities, list):
                for entity in entities:
                    if isinstance(entity, dict):
                        all_entities.append({**entity, "chunk_index": chunk_index})
            if isinstance(relationships, list):
                for relationship in relationships:
                    if isinstance(relationship, dict):
                        all_relationships.append({**relationship, "chunk_index": chunk_index})

        return all_entities, all_relationships

    def _render_source_text(self, docs: list[Document]) -> str:
        parts: list[str] = []
        for index, doc in enumerate(docs, 1):
            text = str(doc.page_content or "").strip()
            if not text:
                continue
            title = str((doc.metadata or {}).get("title") or (doc.metadata or {}).get("source") or f"doc_{index}")
            parts.append(f"### {title}\n{text}")
        return "\n\n".join(parts).strip()

    def _extract_json_object(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start < 0 or end <= start:
                raise
            return json.loads(cleaned[start : end + 1])

    def _normalize_chunks(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, chunk in enumerate(chunks):
            content = str(chunk.get("content") or "").strip()
            if not content:
                continue
            normalized.append(
                {
                    "chunk_index": len(normalized),
                    "title": str(chunk.get("title") or "")[:255],
                    "content": content,
                }
            )
        return normalized

    def _normalize_entities(self, entities: list[dict[str, Any]], chunk_count: int) -> list[dict[str, Any]]:
        seen: set[tuple[int, str]] = set()
        normalized: list[dict[str, Any]] = []
        for entity in entities:
            name = self._clean_name(entity.get("name"))
            if not name:
                continue
            chunk_index = self._safe_chunk_index(entity.get("chunk_index"), chunk_count)
            key = (chunk_index, name.lower())
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                {
                    "chunk_index": chunk_index,
                    "name": name[:255],
                    "entity_type": self._clean_relation_label(entity.get("entity_type") or "concept"),
                    "description": str(entity.get("description") or "")[:500],
                }
            )
        return normalized

    def _normalize_relationships(self, relationships: list[dict[str, Any]], chunk_count: int) -> list[dict[str, Any]]:
        seen: set[tuple[int, str, str, str]] = set()
        normalized: list[dict[str, Any]] = []
        for rel in relationships:
            source = self._clean_name(rel.get("source_entity"))
            target = self._clean_name(rel.get("target_entity"))
            if not source or not target or source == target:
                continue
            chunk_index = self._safe_chunk_index(rel.get("chunk_index"), chunk_count)
            relation_type = self._clean_relation_label(rel.get("relation_type") or "related_to")
            key = (chunk_index, source.lower(), target.lower(), relation_type)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                {
                    "chunk_index": chunk_index,
                    "source_entity": source[:255],
                    "target_entity": target[:255],
                    "relation_type": relation_type,
                    "evidence": str(rel.get("evidence") or "")[:500],
                }
            )
        return normalized

    def _safe_chunk_index(self, value: Any, chunk_count: int) -> int:
        try:
            index = int(value)
        except (TypeError, ValueError):
            return 0
        if chunk_count <= 0:
            return 0
        return max(0, min(index, chunk_count - 1))

    def _clean_name(self, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip(" \t\n\r，。；;：:,.()（）[]【】")).strip()

    def _clean_relation_label(self, value: Any) -> str:
        label = re.sub(r"[^A-Za-z0-9_\-]+", "_", str(value or "").strip().lower()).strip("_")
        return (label or "related_to")[:64]

    def _rule_build_semantic_chunks(self, docs: list[Document]) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        current_title = ""
        current_parts: list[str] = []

        def flush() -> None:
            nonlocal current_parts
            content = "\n\n".join(part.strip() for part in current_parts if part.strip()).strip()
            if content:
                chunks.append({"chunk_index": len(chunks), "title": current_title, "content": content})
            current_parts = []

        for doc in docs:
            text = str(doc.page_content or "").replace("\r\n", "\n").replace("\r", "\n")
            for block in re.split(r"\n{2,}", text):
                block = block.strip()
                if not block:
                    continue
                heading = re.match(r"^#{1,6}\s+(.+)$", block.split("\n", 1)[0].strip())
                if heading and current_parts:
                    flush()
                if heading:
                    current_title = heading.group(1).strip()[:255]
                if sum(len(part) for part in current_parts) + len(block) > MAX_SEMANTIC_CHUNK_CHARS and current_parts:
                    flush()
                current_parts.append(block)
        flush()
        return chunks

    def _rule_extract_graph(self, chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        entities: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        for chunk in chunks:
            chunk_index = int(chunk.get("chunk_index", 0))
            content = str(chunk.get("content") or "")
            names = self._rule_extract_entities(content)
            for name in names:
                entities.append(
                    {
                        "chunk_index": chunk_index,
                        "name": name,
                        "entity_type": "concept",
                        "description": self._rule_entity_description(name, content),
                    }
                )
            for source, target in zip(names, names[1:]):
                relationships.append(
                    {
                        "chunk_index": chunk_index,
                        "source_entity": source,
                        "target_entity": target,
                        "relation_type": "co_occurs",
                        "evidence": content[:500],
                    }
                )
        return entities, relationships

    def _rule_extract_entities(self, text: str) -> list[str]:
        candidates = re.findall(r"[\u4e00-\u9fffA-Za-z0-9][\u4e00-\u9fffA-Za-z0-9_-]{1,24}(?:公司|大学|学院|医院|平台|系统|项目|模型|算法|服务|数据库|知识库|图谱|接口|应用)", text)
        candidates.extend(re.findall(r"\b[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,4}\b", text))
        candidates.extend(re.findall(r"`([^`\n]{2,80})`", text))
        seen: set[str] = set()
        results: list[str] = []
        for candidate in candidates:
            name = self._clean_name(candidate)
            if name and name not in seen:
                seen.add(name)
                results.append(name)
            if len(results) >= 80:
                break
        return results

    def _rule_entity_description(self, name: str, text: str) -> str:
        for sentence in re.split(r"[。！？.!?\n]", text):
            if name in sentence:
                return sentence.strip()[:500]
        return ""


graphrag_demo_service = GraphRAGDemoService()
