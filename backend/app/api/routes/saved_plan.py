from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user_id
from backend.app.core.database import get_db
from backend.app.schemas.common import ApiResponse
from backend.app.schemas.saved_plan import (
    SavedPlanCreate,
    SavedPlanData,
    SavedPlanListData,
    RoutePlanData,
)
from backend.app.services.saved_plan_service import SavedPlanService
from backend.app.services.route_service import RouteService
from project_config import SETTINGS

router = APIRouter()
saved_plan_service = SavedPlanService(redis_url=SETTINGS.redis_url)
route_service = RouteService(redis_url=SETTINGS.redis_url)


@router.get("", response_model=ApiResponse[SavedPlanListData])
async def list_plans(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SavedPlanListData]:
    plans = await saved_plan_service.list_plans(db=db, user_id=user_id)
    return ApiResponse(message="ok", data=SavedPlanListData(plans=[SavedPlanData(**p) for p in plans]))


@router.post("", response_model=ApiResponse[SavedPlanData], status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: SavedPlanCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SavedPlanData]:
    plan = await saved_plan_service.create_plan(db=db, user_id=user_id, payload=payload)
    return ApiResponse(message="计划已保存", data=SavedPlanData(**plan))


@router.put("/{plan_id}", response_model=ApiResponse[SavedPlanData])
async def update_plan(
    plan_id: int,
    payload: SavedPlanCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[SavedPlanData]:
    plan = await saved_plan_service.update_plan(db=db, plan_id=plan_id, user_id=user_id, payload=payload)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="计划不存在")
    return ApiResponse(message="计划已更新", data=SavedPlanData(**plan))


@router.get("/{plan_id}/routes", response_model=ApiResponse[RoutePlanData])
async def get_plan_routes(
    plan_id: int,
    days: str | None = Query(default=None, description="逗号分隔的天编号，如 1,2,3"),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[RoutePlanData]:
    day_list = None
    if days:
        try:
            day_list = [int(d.strip()) for d in days.split(",") if d.strip()]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="days 参数格式错误，应为逗号分隔的数字",
            )

    result = await route_service.get_plan_routes(
        db=db, plan_id=plan_id, user_id=user_id, days=day_list,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="计划不存在",
        )
    return ApiResponse(message="ok", data=RoutePlanData(**result))


@router.delete("/{plan_id}", response_model=ApiResponse[None])
async def delete_plan(
    plan_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    ok = await saved_plan_service.delete_plan(db=db, plan_id=plan_id, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="计划不存在")
    return ApiResponse(message="计划已删除", data=None)
