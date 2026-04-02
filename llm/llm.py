"""Load LLM runtime environment variables."""

import os
from pathlib import Path

import dotenv


_ENV_PATH = Path(__file__).resolve().parent / ".env"
dotenv.load_dotenv(dotenv_path=_ENV_PATH)


def _parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _apply_proxy_env() -> None:
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        value = os.getenv(key) or os.getenv(key.lower())
        if not value:
            continue
        normalized = value.strip()
        os.environ[key] = normalized
        os.environ[key.lower()] = normalized


def read_llm() -> None:
    api_key = os.getenv("OPENAI_API_KEY1") or os.getenv("OPENAI_API_KEY")
    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip()
    langsmith_tracing = _parse_bool(os.getenv("LANGSMITH_TRACING"), False)

    if not api_key:
        raise RuntimeError("Missing OpenAI API key. Set OPENAI_API_KEY1 or OPENAI_API_KEY in llm/.env")

    _apply_proxy_env()
    os.environ["OPENAI_API_KEY"] = api_key
    if base_url:
        os.environ["OPENAI_BASE_URL"] = base_url.rstrip("/")

    # Keep LangSmith tracing opt-in for local runs and remove inherited flags when disabled.
    if langsmith_tracing:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
    else:
        for key in (
            "LANGSMITH_TRACING",
            "LANGCHAIN_TRACING_V2",
            "LANGCHAIN_TRACING",
            "LANGSMITH_ENDPOINT",
            "LANGSMITH_API_KEY",
            "LANGSMITH_PROJECT",
        ):
            os.environ.pop(key, None)
