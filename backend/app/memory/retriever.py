from __future__ import annotations

import re

from .long_term import LongTermMemoryStore
from .schemas import RetrievedMemory


class MarkdownMemoryRetriever:
    def __init__(self, store: LongTermMemoryStore | None = None) -> None:
        self.store = store or LongTermMemoryStore()

    def retrieve(self, query: str, top_k: int = 4) -> list[RetrievedMemory]:
        keywords = self._keywords(query)
        if not keywords:
            return []

        results: list[RetrievedMemory] = []
        for block in self.store.load_blocks():
            haystack = f"{block.file} {block.section} {block.content}".lower()
            score = sum(1 for keyword in keywords if keyword in haystack)
            if score > 0:
                results.append(
                    RetrievedMemory(
                        file=block.file,
                        section=block.section,
                        content=block.content,
                        score=float(score),
                    )
                )

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]

    @staticmethod
    def _keywords(text: str) -> set[str]:
        lowered = text.lower()
        latin = set(re.findall(r"[a-z0-9_./\\-]{2,}", lowered))
        chinese = set(re.findall(r"[\u4e00-\u9fff]{2,}", lowered))
        return latin | chinese

