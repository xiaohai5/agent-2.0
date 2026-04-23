from __future__ import annotations

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import ForeignKey

from backend.app.models import Base


class GraphSemanticChunk(Base):
    __tablename__ = "graph_semantic_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_graph_semantic_chunk_document_index"),
    )


class GraphEntity(Base):
    __tablename__ = "graph_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("graph_semantic_chunks.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, default="concept")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")


class GraphRelationship(Base):
    __tablename__ = "graph_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("graph_semantic_chunks.id"), nullable=True, index=True)
    source_entity: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_entity: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False, default="related_to")
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="")
