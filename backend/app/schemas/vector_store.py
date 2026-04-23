from __future__ import annotations

from pydantic import BaseModel


class GraphIngestData(BaseModel):
    semantic_chunks: int = 0
    entities: int = 0
    relationships: int = 0


class UploadData(BaseModel):
    filename: str
    status: str
    message: str | None = None
    graph: GraphIngestData | None = None


class DocumentItem(BaseModel):
    id: int
    filename: str
    status: str


class GraphChunkItem(BaseModel):
    id: int
    filename: str
    chunk_index: int
    title: str
    content_preview: str


class GraphEntityItem(BaseModel):
    id: int
    name: str
    entity_type: str
    description: str


class GraphRelationshipItem(BaseModel):
    id: int
    source_entity: str
    target_entity: str
    relation_type: str
    evidence: str


class GraphSummaryData(BaseModel):
    semantic_chunk_count: int
    entity_count: int
    relationship_count: int
    chunks: list[GraphChunkItem]
    entities: list[GraphEntityItem]
    relationships: list[GraphRelationshipItem]
