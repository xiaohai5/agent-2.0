from dataclasses import dataclass
from typing import Any


@dataclass
class SplitterConfig:
    chunk_size: int = 500
    chunk_overlap: int = 50
    table_row_batch_size: int = 5
    table_row_overlap: int = 1
    top_k: int = 5

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "SplitterConfig":
        if not data:
            return cls()
        return cls(
            chunk_size=int(data.get("chunk_size", cls.chunk_size)),
            chunk_overlap=int(data.get("chunk_overlap", cls.chunk_overlap)),
            table_row_batch_size=int(data.get("table_row_batch_size", cls.table_row_batch_size)),
            table_row_overlap=int(data.get("table_row_overlap", cls.table_row_overlap)),
            top_k=int(data.get("top_k", cls.top_k)),
        )

    def get_config(self) -> tuple[int, int, int, int, int]:
        return (
            self.chunk_size,
            self.chunk_overlap,
            self.table_row_batch_size,
            self.table_row_overlap,
            self.top_k,
        )
