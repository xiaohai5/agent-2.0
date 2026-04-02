from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.crued.travel_plan import (
    archive_plan,
    confirm_plan,
    get_user_plan_detail,
    list_user_plans,
)
from backend.app.crued.user import verify_token
from backend.app.schemas.travel_plan import (
    TravelPlanConfirmRequest,
    TravelPlanDetail,
    TravelPlanListResponse,
)
from backend.app.utils.user import parse_bearer_token


router = APIRouter()


@router.get("", response_model=TravelPlanListResponse)
async def get_travel_plans(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> TravelPlanListResponse:
    token = parse_bearer_token(authorization)
    user_id = await verify_token(token, db)
    items = await list_user_plans(db, user_id)
    return TravelPlanListResponse(items=items)


@router.get("/{plan_id}", response_model=TravelPlanDetail)
async def get_travel_plan_detail(
    plan_id: int,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> TravelPlanDetail:
    token = parse_bearer_token(authorization)
    user_id = await verify_token(token, db)
    detail = await get_user_plan_detail(db, user_id, plan_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="出行计划不存在")
    return detail


@router.post("/{plan_id}/confirm", response_model=TravelPlanDetail)
async def confirm_travel_plan(
    plan_id: int,
    payload: TravelPlanConfirmRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> TravelPlanDetail:
    token = parse_bearer_token(authorization)
    user_id = await verify_token(token, db)
    detail = await get_user_plan_detail(db, user_id, plan_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="出行计划不存在")

    await confirm_plan(db, plan_id, payload.final_payload)
    confirmed = await get_user_plan_detail(db, user_id, plan_id)
    if not confirmed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="出行计划不存在")
    return confirmed


@router.post("/{plan_id}/archive", response_model=TravelPlanDetail)
async def archive_travel_plan(
    plan_id: int,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> TravelPlanDetail:
    token = parse_bearer_token(authorization)
    user_id = await verify_token(token, db)
    detail = await get_user_plan_detail(db, user_id, plan_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="出行计划不存在")

    await archive_plan(db, plan_id)
    archived = await get_user_plan_detail(db, user_id, plan_id)
    if not archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="出行计划不存在")
    return archived
