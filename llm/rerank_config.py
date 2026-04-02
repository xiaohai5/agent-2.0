from dataclasses import dataclass
from typing import Any


@dataclass
class RerankConfig:
    enabled: bool = True
    top_k: int = 10
    model_name: str = "BAAI/bge-reranker-v2-m3"
    device: str = "cuda:0"
    use_fp16: bool = True
    normalize: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "RerankConfig":
        if not data:
            return cls()
        return cls(
            enabled=bool(data.get("rerank_enabled", data.get("enabled", cls.enabled))),
            top_k=int(data.get("rerank_top_k", data.get("top_k", cls.top_k))),
            model_name=str(data.get("rerank_model_name", cls.model_name)),
            device=str(data.get("rerank_device", data.get("device", cls.device))),
            use_fp16=bool(data.get("rerank_use_fp16", cls.use_fp16)),
            normalize=bool(data.get("rerank_normalize", cls.normalize)),
        )

    def get_config(self) -> tuple[bool, int, str, str, bool, bool]:
        return self.enabled, self.top_k, self.model_name, self.device, self.use_fp16, self.normalize
