"""Apply centralized runtime environment variables."""

from project_config import apply_runtime_environment


def read_llm() -> None:
    apply_runtime_environment()
