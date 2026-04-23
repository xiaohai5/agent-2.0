from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.graphrag import GraphEntity, GraphRelationship, GraphSemanticChunk


@dataclass(slots=True)
class KGEvidence:
    source_entity: str
    relation_type: str
    target_entity: str
    evidence: str
    chunk_preview: str
    score: int


class LightweightKGRetriever:
    async def retrieve(self, db: AsyncSession, *, user_id: int, query: str, top_k: int = 5) -> str:
        query_text = str(query or "").strip()
        if not query_text:
            return "No KG query provided."

        keywords = self._extract_keywords(query_text)
        if not keywords:
            return "No KG keywords extracted."

        local_evidence = await self._local_relation_recall(db, user_id=user_id, keywords=keywords, top_k=top_k)
        if not local_evidence:
            local_evidence = await self._topic_relation_recall(db, user_id=user_id, keywords=keywords, top_k=top_k)

        if not local_evidence:
            return "No related KG evidence found."

        lines = []
        for index, item in enumerate(local_evidence[:top_k], 1):
            lines.append(
                "\n".join(
                    [
                        f"[KG-{index}] {item.source_entity} --{item.relation_type}--> {item.target_entity}",
                        f"score={item.score}",
                        f"evidence: {item.evidence or item.chunk_preview}",
                    ]
                )
            )
        return "\n\n".join(lines)

    async def _local_relation_recall(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        keywords: list[str],
        top_k: int,
    ) -> list[KGEvidence]:
        entity_conditions = [GraphEntity.name.ilike(f"%{keyword}%") for keyword in keywords]
        entity_result = await db.execute(
            select(GraphEntity.name)
            .where(GraphEntity.user_id == user_id, or_(*entity_conditions))
            .limit(max(top_k * 4, 20))
        )
        entity_names = [name for name in entity_result.scalars().all() if name]
        if not entity_names:
            return []

        relation_conditions = []
        for name in entity_names:
            relation_conditions.append(GraphRelationship.source_entity == name)
            relation_conditions.append(GraphRelationship.target_entity == name)

        result = await db.execute(
            select(GraphRelationship, GraphSemanticChunk)
            .outerjoin(GraphSemanticChunk, GraphRelationship.chunk_id == GraphSemanticChunk.id)
            .where(GraphRelationship.user_id == user_id, or_(*relation_conditions))
            .limit(max(top_k * 8, 40))
        )
        return self._rank_relationship_rows(result.all(), keywords, top_k)

    async def _topic_relation_recall(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        keywords: list[str],
        top_k: int,
    ) -> list[KGEvidence]:
        chunk_conditions = []
        for keyword in keywords:
            chunk_conditions.append(GraphSemanticChunk.title.ilike(f"%{keyword}%"))
            chunk_conditions.append(GraphSemanticChunk.content.ilike(f"%{keyword}%"))

        chunk_result = await db.execute(
            select(GraphSemanticChunk.id)
            .where(GraphSemanticChunk.user_id == user_id, or_(*chunk_conditions))
            .limit(max(top_k * 4, 20))
        )
        chunk_ids = [chunk_id for chunk_id in chunk_result.scalars().all() if chunk_id]
        if not chunk_ids:
            return []

        result = await db.execute(
            select(GraphRelationship, GraphSemanticChunk)
            .outerjoin(GraphSemanticChunk, GraphRelationship.chunk_id == GraphSemanticChunk.id)
            .where(GraphRelationship.user_id == user_id, GraphRelationship.chunk_id.in_(chunk_ids))
            .limit(max(top_k * 8, 40))
        )
        return self._rank_relationship_rows(result.all(), keywords, top_k)

    def _rank_relationship_rows(self, rows: Iterable[tuple[GraphRelationship, GraphSemanticChunk | None]], keywords: list[str], top_k: int) -> list[KGEvidence]:
        ranked: list[KGEvidence] = []
        seen: set[tuple[str, str, str]] = set()

        for relationship, chunk in rows:
            key = (relationship.source_entity, relationship.relation_type, relationship.target_entity)
            if key in seen:
                continue
            seen.add(key)

            evidence = str(relationship.evidence or "")
            chunk_preview = str(getattr(chunk, "content", "") or "")[:300]
            score = self._score_relationship(relationship, evidence, chunk_preview, keywords)
            ranked.append(
                KGEvidence(
                    source_entity=relationship.source_entity,
                    relation_type=relationship.relation_type,
                    target_entity=relationship.target_entity,
                    evidence=evidence[:500],
                    chunk_preview=chunk_preview,
                    score=score,
                )
            )

        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:top_k]

    def _score_relationship(self, relationship: GraphRelationship, evidence: str, chunk_preview: str, keywords: list[str]) -> int:
        source = relationship.source_entity.lower()
        target = relationship.target_entity.lower()
        relation_type = relationship.relation_type.lower()
        evidence_text = evidence.lower()
        chunk_text = chunk_preview.lower()

        score = 0
        for keyword in keywords:
            lowered = keyword.lower()
            if lowered in source:
                score += 3
            if lowered in target:
                score += 3
            if lowered in relation_type:
                score += 2
            if lowered in evidence_text:
                score += 1
            if lowered in chunk_text:
                score += 1
        return score

    def _extract_keywords(self, query: str) -> list[str]:
        candidates: list[str] = []
        candidates.extend(re.findall(r"[\u4e00-\u9fffA-Za-z0-9][\u4e00-\u9fffA-Za-z0-9_-]{1,24}", query))
        candidates.extend(re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{1,40}\b", query))

        stopwords = {
            "what",
            "which",
            "where",
            "when",
            "how",
            "why",
            "the",
            "and",
            "or",
            "is",
            "are",
            "to",
            "of",
            "in",
            "关系",
            "什么",
            "怎么",
            "如何",
            "以及",
            "这个",
            "那个",
        }
        seen: set[str] = set()
        keywords: list[str] = []
        for candidate in candidates:
            keyword = candidate.strip(" \t\n\r，。；;：:,.()（）[]【】")
            if len(keyword) < 2 or keyword.lower() in stopwords or keyword in seen:
                continue
            seen.add(keyword)
            keywords.append(keyword)
            if len(keywords) >= 8:
                break
        return keywords


lightweight_kg_retriever = LightweightKGRetriever()
