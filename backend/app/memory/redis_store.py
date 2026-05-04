from __future__ import annotations

import dataclasses
import json
from typing import Any

from project_config import SETTINGS


class RedisShortTermMemoryStore:
    _fallback: dict[str, dict[str, Any]] = {}

    def __init__(self, redis_url: str | None = None, ttl_seconds: int | None = None) -> None:
        self.redis_url = redis_url or SETTINGS.redis_url
        self.ttl_seconds = ttl_seconds or SETTINGS.short_memory_ttl_seconds
        self._client: Any | None = None

    async def get(self, user_id: int, conversation_id: str | None) -> dict[str, Any] | None:
        key = self._key(user_id, conversation_id)
        client = await self._get_client()
        if client is None:
            data = self._fallback.get(key)
            return dict(data) if data else None

        raw = await client.get(key)
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    async def set(self, user_id: int, conversation_id: str | None, memory_state: dict[str, Any]) -> None:
        key = self._key(user_id, conversation_id)
        payload = json.dumps(self._serialize(memory_state), ensure_ascii=False)
        client = await self._get_client()
        if client is None:
            self._fallback[key] = json.loads(payload)
            return
        await client.set(key, payload, ex=self.ttl_seconds)

    async def delete(self, user_id: int, conversation_id: str | None = None) -> None:
        key = self._key(user_id, conversation_id)
        client = await self._get_client()
        if client is None:
            self._fallback.pop(key, None)
            return
        await client.delete(key)

    async def _get_client(self) -> Any | None:
        if self._client is not None:
            return self._client
        try:
            from redis.asyncio import Redis

            client = Redis.from_url(self.redis_url, decode_responses=True)
            await client.ping()
            self._client = client
            return client
        except Exception:
            self._client = None
            return None

    @staticmethod
    def _key(user_id: int, conversation_id: str | None) -> str:
        cid = conversation_id or "default"
        safe_cid = "".join(ch if ch.isalnum() or ch in "-_:" else "_" for ch in cid)
        return f"agent:short_memory:{user_id}:{safe_cid}"

    def _serialize(self, obj: Any) -> Any:
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return {k: self._serialize(v) for k, v in dataclasses.asdict(obj).items()}
        if isinstance(obj, dict):
            return {k: self._serialize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._serialize(item) for item in obj]
        if isinstance(obj, tuple):
            return [self._serialize(item) for item in obj]
        return obj

