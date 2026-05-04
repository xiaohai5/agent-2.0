from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MemoryBlock:
    file: str
    section: str
    content: str


@dataclass(slots=True)
class RetrievedMemory:
    file: str
    section: str
    content: str
    score: float


@dataclass(slots=True)
class MemoryUpdate:
    action: str
    file: str
    section: str
    content: str
    confidence: float = 1.0

