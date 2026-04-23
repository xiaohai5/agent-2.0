from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.graphrag import GraphEntity, GraphRelationship, GraphSemanticChunk


@dataclass(slots=True)
class GraphIngestStats:
    semantic_chunks: int
    entities: int
    relationships: int


async def replace_document_graph(
    db: AsyncSession,
    *,
    user_id: int,
    document_id: int,
    filename: str,
    chunks: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> GraphIngestStats:
    await delete_document_graph(db, user_id=user_id, document_id=document_id)

    chunk_models: list[GraphSemanticChunk] = []
    chunk_id_by_index: dict[int, int] = {}
    for chunk in chunks:
        model = GraphSemanticChunk(
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            chunk_index=int(chunk["chunk_index"]),
            title=str(chunk.get("title") or ""),
            content=str(chunk.get("content") or ""),
        )
        db.add(model)
        chunk_models.append(model)

    await db.flush()
    for model in chunk_models:
        chunk_id_by_index[model.chunk_index] = model.id

    entity_models = [
        GraphEntity(
            user_id=user_id,
            document_id=document_id,
            chunk_id=chunk_id_by_index.get(int(entity.get("chunk_index", -1))),
            name=str(entity.get("name") or ""),
            entity_type=str(entity.get("entity_type") or "concept"),
            description=str(entity.get("description") or ""),
        )
        for entity in entities
        if str(entity.get("name") or "").strip()
    ]
    db.add_all(entity_models)

    relationship_models = [
        GraphRelationship(
            user_id=user_id,
            document_id=document_id,
            chunk_id=chunk_id_by_index.get(int(rel.get("chunk_index", -1))),
            source_entity=str(rel.get("source_entity") or ""),
            target_entity=str(rel.get("target_entity") or ""),
            relation_type=str(rel.get("relation_type") or "related_to"),
            evidence=str(rel.get("evidence") or ""),
        )
        for rel in relationships
        if str(rel.get("source_entity") or "").strip() and str(rel.get("target_entity") or "").strip()
    ]
    db.add_all(relationship_models)
    await db.flush()

    return GraphIngestStats(
        semantic_chunks=len(chunk_models),
        entities=len(entity_models),
        relationships=len(relationship_models),
    )


async def delete_document_graph(db: AsyncSession, *, user_id: int, document_id: int) -> None:
    await db.execute(
        delete(GraphRelationship).where(
            GraphRelationship.user_id == user_id,
            GraphRelationship.document_id == document_id,
        )
    )
    await db.execute(
        delete(GraphEntity).where(
            GraphEntity.user_id == user_id,
            GraphEntity.document_id == document_id,
        )
    )
    await db.execute(
        delete(GraphSemanticChunk).where(
            GraphSemanticChunk.user_id == user_id,
            GraphSemanticChunk.document_id == document_id,
        )
    )
    await db.flush()


async def get_document_graph_summary(db: AsyncSession, *, user_id: int, filename: str | None = None) -> dict[str, Any]:
    chunk_query = select(GraphSemanticChunk).where(GraphSemanticChunk.user_id == user_id)
    entity_query = select(GraphEntity).where(GraphEntity.user_id == user_id)
    rel_query = select(GraphRelationship).where(GraphRelationship.user_id == user_id)

    if filename:
        chunk_query = chunk_query.where(GraphSemanticChunk.filename == filename)
        document_ids = select(GraphSemanticChunk.document_id).where(
            GraphSemanticChunk.user_id == user_id,
            GraphSemanticChunk.filename == filename,
        )
        entity_query = entity_query.where(GraphEntity.document_id.in_(document_ids))
        rel_query = rel_query.where(GraphRelationship.document_id.in_(document_ids))

    chunks = list((await db.execute(chunk_query.order_by(GraphSemanticChunk.id.desc()).limit(20))).scalars().all())
    entities = list((await db.execute(entity_query.order_by(GraphEntity.id.desc()).limit(50))).scalars().all())
    relationships = list((await db.execute(rel_query.order_by(GraphRelationship.id.desc()).limit(50))).scalars().all())

    count_chunk_query = select(func.count()).select_from(chunk_query.subquery())
    count_entity_query = select(func.count()).select_from(entity_query.subquery())
    count_rel_query = select(func.count()).select_from(rel_query.subquery())

    return {
        "semantic_chunk_count": int((await db.execute(count_chunk_query)).scalar_one()),
        "entity_count": int((await db.execute(count_entity_query)).scalar_one()),
        "relationship_count": int((await db.execute(count_rel_query)).scalar_one()),
        "chunks": [
            {
                "id": item.id,
                "filename": item.filename,
                "chunk_index": item.chunk_index,
                "title": item.title,
                "content_preview": item.content[:240],
            }
            for item in chunks
        ],
        "entities": [
            {
                "id": item.id,
                "name": item.name,
                "entity_type": item.entity_type,
                "description": item.description,
            }
            for item in entities
        ],
        "relationships": [
            {
                "id": item.id,
                "source_entity": item.source_entity,
                "target_entity": item.target_entity,
                "relation_type": item.relation_type,
                "evidence": item.evidence,
            }
            for item in relationships
        ],
    }
