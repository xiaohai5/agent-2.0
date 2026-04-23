from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ModuleName = Literal["travel_planning", "ticket_service", "hotel_restaurant", "rag", "general_chat"]


@dataclass(slots=True)
class SkillReference:
    module: ModuleName
    path: str
    title: str


@dataclass(slots=True)
class SkillMetadata:
    name: str
    description: str
    path: str
    references: dict[ModuleName, SkillReference] = field(default_factory=dict)

