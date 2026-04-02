from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.travel_plan import TravelPlan, TravelPlanLockedItem
from backend.app.schemas.travel_plan import TravelPlanCard, TravelPlanDetail, TravelPlanLockItem


ACTIVE_STATUSES = {"draft", "ready_for_confirmation"}
ARCHIVED_STATUSES = {"confirmed", "archived"}


def _copy_dict(value: dict[str, Any] | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _normalize_title(plan: TravelPlan) -> str:
    destination = (plan.destination or "").strip()
    departure_date = (plan.departure_date or "").strip()
    if destination and departure_date:
        return f"{destination} {departure_date} 出行计划"
    if destination:
        return f"{destination} 出行计划"
    return plan.title or "未命名出行计划"


def _normalize_plan_fields(plan: TravelPlan, payload: dict[str, Any]) -> None:
    plan.origin = str(payload.get("origin", plan.origin or "")).strip() or None
    plan.destination = str(payload.get("destination", plan.destination or "")).strip() or None
    plan.departure_date = str(payload.get("departure_date", plan.departure_date or "")).strip() or None
    plan.return_date = str(payload.get("return_date", plan.return_date or "")).strip() or None

    travelers = payload.get("travelers", plan.travelers)
    if isinstance(travelers, str) and travelers.strip().isdigit():
        travelers = int(travelers.strip())
    plan.travelers = travelers if isinstance(travelers, int) else None

    plan.budget = str(payload.get("budget", plan.budget or "")).strip() or None
    summary = payload.get("plan_summary", payload.get("summary", plan.plan_summary or ""))
    plan.plan_summary = str(summary).strip() or None
    plan.title = _normalize_title(plan)


async def get_or_create_active_plan(db: AsyncSession, user_id: int) -> TravelPlan:
    result = await db.execute(
        select(TravelPlan)
        .where(TravelPlan.user_id == user_id, TravelPlan.status.in_(ACTIVE_STATUSES))
        .order_by(TravelPlan.updated_at.desc())
    )
    plan = result.scalars().first()
    if plan:
        return plan

    plan = TravelPlan(user_id=user_id, title="未命名出行计划", status="draft", source="chat")
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def get_plan_by_id_for_user(db: AsyncSession, user_id: int, plan_id: int) -> TravelPlan | None:
    result = await db.execute(
        select(TravelPlan).where(TravelPlan.id == plan_id, TravelPlan.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_plan_draft(db: AsyncSession, plan_id: int, draft_data: dict[str, Any]) -> TravelPlan:
    plan = await db.get(TravelPlan, plan_id)
    if not plan:
        raise ValueError("Travel plan not found")

    merged = _copy_dict(plan.draft_data)
    merged.update(_copy_dict(draft_data))
    plan.draft_data = merged
    _normalize_plan_fields(plan, merged)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def lock_plan_field(
    db: AsyncSession,
    plan_id: int,
    field_name: str,
    field_value: Any,
    source_message: str | None = None,
    field_type: str = "selection",
) -> TravelPlanLockedItem:
    plan = await db.get(TravelPlan, plan_id)
    if not plan:
        raise ValueError("Travel plan not found")

    result = await db.execute(
        select(TravelPlanLockedItem).where(
            TravelPlanLockedItem.plan_id == plan_id,
            TravelPlanLockedItem.field_name == field_name,
            TravelPlanLockedItem.is_active.is_(True),
        )
    )
    existing_items = result.scalars().all()
    for item in existing_items:
        item.is_active = False
        db.add(item)

    locked_item = TravelPlanLockedItem(
        plan_id=plan_id,
        field_name=field_name,
        field_type=field_type,
        field_value=field_value,
        source_message=source_message,
        is_active=True,
    )
    db.add(locked_item)

    locked_data = _copy_dict(plan.locked_data)
    locked_data[field_name] = field_value
    plan.locked_data = locked_data
    db.add(plan)
    await db.commit()
    await db.refresh(locked_item)
    return locked_item


async def unlock_plan_field(db: AsyncSession, plan_id: int, field_name: str) -> None:
    plan = await db.get(TravelPlan, plan_id)
    if not plan:
        raise ValueError("Travel plan not found")

    result = await db.execute(
        select(TravelPlanLockedItem).where(
            TravelPlanLockedItem.plan_id == plan_id,
            TravelPlanLockedItem.field_name == field_name,
            TravelPlanLockedItem.is_active.is_(True),
        )
    )
    for item in result.scalars().all():
        item.is_active = False
        db.add(item)

    locked_data = _copy_dict(plan.locked_data)
    if field_name in locked_data:
        locked_data.pop(field_name, None)
        plan.locked_data = locked_data
        db.add(plan)
    await db.commit()


async def mark_plan_ready_for_confirmation(
    db: AsyncSession,
    plan_id: int,
    final_payload: dict[str, Any],
) -> TravelPlan:
    plan = await db.get(TravelPlan, plan_id)
    if not plan:
        raise ValueError("Travel plan not found")

    plan.status = "ready_for_confirmation"
    plan.final_confirmed_data = _copy_dict(final_payload)
    _normalize_plan_fields(plan, final_payload)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def confirm_plan(
    db: AsyncSession,
    plan_id: int,
    final_payload: dict[str, Any],
) -> TravelPlan:
    plan = await db.get(TravelPlan, plan_id)
    if not plan:
        raise ValueError("Travel plan not found")

    payload = _copy_dict(plan.final_confirmed_data)
    payload.update(_copy_dict(final_payload))
    plan.status = "confirmed"
    plan.final_confirmed_data = payload
    plan.confirmed_at = datetime.now()
    _normalize_plan_fields(plan, payload)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def archive_plan(db: AsyncSession, plan_id: int) -> TravelPlan:
    plan = await db.get(TravelPlan, plan_id)
    if not plan:
        raise ValueError("Travel plan not found")
    plan.status = "archived"
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def list_user_plans(db: AsyncSession, user_id: int) -> list[TravelPlanCard]:
    result = await db.execute(
        select(
            TravelPlan,
            func.count(TravelPlanLockedItem.id).label("locked_item_count"),
        )
        .outerjoin(
            TravelPlanLockedItem,
            (TravelPlanLockedItem.plan_id == TravelPlan.id) & (TravelPlanLockedItem.is_active.is_(True)),
        )
        .where(TravelPlan.user_id == user_id)
        .group_by(TravelPlan.id)
        .order_by(TravelPlan.updated_at.desc())
    )

    cards: list[TravelPlanCard] = []
    for plan, locked_item_count in result.all():
        cards.append(
            TravelPlanCard(
                id=plan.id,
                title=_normalize_title(plan),
                status=plan.status,
                origin=plan.origin,
                destination=plan.destination,
                departure_date=plan.departure_date,
                return_date=plan.return_date,
                travelers=plan.travelers,
                budget=plan.budget,
                summary=plan.plan_summary,
                confirmed_at=plan.confirmed_at,
                locked_item_count=int(locked_item_count or 0),
            )
        )
    return cards


async def get_user_plan_detail(db: AsyncSession, user_id: int, plan_id: int) -> TravelPlanDetail | None:
    plan = await get_plan_by_id_for_user(db, user_id, plan_id)
    if not plan:
        return None

    result = await db.execute(
        select(TravelPlanLockedItem)
        .where(TravelPlanLockedItem.plan_id == plan.id)
        .order_by(TravelPlanLockedItem.locked_at.desc())
    )
    locked_items = [
        TravelPlanLockItem(
            field_name=item.field_name,
            field_type=item.field_type,
            field_value=item.field_value,
            source_message=item.source_message,
            is_active=item.is_active,
            locked_at=item.locked_at,
        )
        for item in result.scalars().all()
    ]

    return TravelPlanDetail(
        id=plan.id,
        title=_normalize_title(plan),
        status=plan.status,
        source=plan.source,
        origin=plan.origin,
        destination=plan.destination,
        departure_date=plan.departure_date,
        return_date=plan.return_date,
        travelers=plan.travelers,
        budget=plan.budget,
        plan_summary=plan.plan_summary,
        draft_data=_copy_dict(plan.draft_data),
        locked_data=_copy_dict(plan.locked_data),
        final_confirmed_data=_copy_dict(plan.final_confirmed_data),
        confirmed_at=plan.confirmed_at,
        locked_items=locked_items,
    )
