from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.crued import saved_plan as plan_crud
from backend.app.schemas.saved_plan import SavedPlanCreate, SavedPlanData

PLAN_CACHE_TTL_SECONDS = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class SavedPlanService:
    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url
        self._redis: Redis | None = None

    async def _get_redis(self) -> Redis | None:
        if self._redis is not None:
            return self._redis
        if not self.redis_url:
            return None
        try:
            from redis.asyncio import Redis as R

            client = R.from_url(self.redis_url, decode_responses=True)
            await client.ping()
            self._redis = client
            return client
        except Exception:
            self._redis = None
            return None

    # -- cache helpers -------------------------------------------------------

    @staticmethod
    def _cache_key(user_id: int) -> str:
        return f"agent:saved_plans:{user_id}"

    async def _invalidate_cache(self, user_id: int) -> None:
        r = await self._get_redis()
        if r:
            await r.delete(self._cache_key(user_id))

    # -- CRUD ---------------------------------------------------------------

    async def list_plans(self, db: AsyncSession, user_id: int) -> list[dict[str, Any]]:
        r = await self._get_redis()
        if r:
            cached = await r.get(self._cache_key(user_id))
            if cached:
                return json.loads(cached)

        plans = await plan_crud.get_user_plans(db, user_id)
        result = [_plan_to_dict(p) for p in plans]

        if r:
            await r.set(
                self._cache_key(user_id),
                json.dumps(result, ensure_ascii=False, default=str),
                ex=PLAN_CACHE_TTL_SECONDS,
            )

        return result

    async def create_plan(
        self,
        db: AsyncSession,
        user_id: int,
        payload: SavedPlanCreate,
    ) -> dict[str, Any]:
        plan_data = {
            "days": [d.model_dump() for d in payload.days],
            "overview": payload.overview,
            "title": payload.title,
        }
        plan = await plan_crud.create_plan(
            db=db,
            user_id=user_id,
            title=payload.title,
            plan_data=plan_data,
            source_message_id=payload.source_message_id,
            overview=payload.overview,
        )
        await self._invalidate_cache(user_id)

        return _plan_to_dict(plan)

    async def delete_plan(self, db: AsyncSession, plan_id: int, user_id: int) -> bool:
        ok = await plan_crud.delete_plan(db, plan_id, user_id)
        if ok:
            await self._invalidate_cache(user_id)
        return ok

    async def update_plan(
        self,
        db: AsyncSession,
        plan_id: int,
        user_id: int,
        payload: SavedPlanCreate,
    ) -> dict[str, Any] | None:
        plan = await plan_crud.update_plan(
            db=db,
            plan_id=plan_id,
            user_id=user_id,
            title=payload.title,
            plan_data={
                "days": [d.model_dump() for d in payload.days],
                "overview": payload.overview,
                "title": payload.title,
            },
            source_message_id=payload.source_message_id,
            overview=payload.overview,
        )
        if plan:
            await self._invalidate_cache(user_id)
            return _plan_to_dict(plan)
        return None


def _plan_to_dict(plan) -> dict[str, Any]:
    return {
        "id": plan.id,
        "user_id": plan.user_id,
        "title": plan.title,
        "plan_data": plan.plan_data or {},
        "source_message_id": plan.source_message_id,
        "overview": plan.overview or "",
        "created_at": plan.created_at.isoformat() if plan.created_at else "",
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else "",
    }
