"""Retriever factory."""

try:
    from .hybrid_retriever import FirstLayerHybridRetriever
except ImportError:
    from hybrid_retriever import FirstLayerHybridRetriever


def creat_retriver(splitter_params: dict | None = None, collection_name: str | None = None):
    return FirstLayerHybridRetriever(splitter_params, collection_name=collection_name)
