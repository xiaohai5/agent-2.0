from __future__ import annotations

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.saved_plan import SavedPlan


async def create_plan(
    db: AsyncSession,
    user_id: int,
    title: str,
    plan_data: dict,
    source_message_id: str | None = None,
    overview: str | None = None,
) -> SavedPlan:
    plan = SavedPlan(
        user_id=user_id,
        title=title,
        plan_data=plan_data,
        source_message_id=source_message_id,
        overview=overview,
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return plan


async def get_user_plans(db: AsyncSession, user_id: int) -> list[SavedPlan]:
    result = await db.execute(
        select(SavedPlan)
        .where(SavedPlan.user_id == user_id)
        .order_by(SavedPlan.created_at.desc())
    )
    return list(result.scalars().all())


async def get_plan_by_id(db: AsyncSession, plan_id: int, user_id: int) -> SavedPlan | None:
    result = await db.execute(
        select(SavedPlan).where(SavedPlan.id == plan_id, SavedPlan.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def delete_plan(db: AsyncSession, plan_id: int, user_id: int) -> bool:
    result = await db.execute(
        delete(SavedPlan).where(SavedPlan.id == plan_id, SavedPlan.user_id == user_id)
    )
    await db.flush()
    return result.rowcount > 0


async def update_plan(
    db: AsyncSession,
    plan_id: int,
    user_id: int,
    title: str,
    plan_data: dict,
    source_message_id: str | None = None,
    overview: str | None = None,
) -> SavedPlan | None:
    result = await db.execute(
        select(SavedPlan).where(SavedPlan.id == plan_id, SavedPlan.user_id == user_id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        return None
    plan.title = title
    plan.plan_data = plan_data
    plan.source_message_id = source_message_id
    plan.overview = overview
    await db.flush()
    await db.refresh(plan)
    return plan
