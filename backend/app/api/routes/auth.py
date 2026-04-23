from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user_id
from backend.app.core.database import get_db
from backend.app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MessageData,
    RegisterRequest,
    TokenData,
    UserProfileData,
)
from backend.app.schemas.common import ApiResponse
from backend.app.services.auth_service import auth_service


router = APIRouter()


@router.post("/register", response_model=ApiResponse[TokenData], status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> ApiResponse[TokenData]:
    data = await auth_service.register(
        db=db,
        username=payload.username,
        email=payload.email,
        password=payload.password,
    )
    return ApiResponse(message="注册成功", data=TokenData(**data))


@router.post("/login", response_model=ApiResponse[TokenData])
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> ApiResponse[TokenData]:
    data = await auth_service.login(db=db, username=payload.username, password=payload.password)
    return ApiResponse(message="登录成功", data=TokenData(**data))


@router.get("/profile", response_model=ApiResponse[UserProfileData])
async def get_profile(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
) -> ApiResponse[UserProfileData]:
    data = await auth_service.get_profile(db=db, user_id=user_id)
    return ApiResponse(message="获取个人资料成功", data=UserProfileData(**data))


@router.post("/change-password", response_model=ApiResponse[MessageData])
async def change_password(
    payload: ChangePasswordRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[MessageData]:
    await auth_service.change_password(
        db=db,
        user_id=user_id,
        username=payload.username,
        old_password=payload.old_password,
        new_password=payload.new_password,
        confirm_password=payload.confirm_password,
    )
    return ApiResponse(message="密码修改成功", data=MessageData(message="密码已更新"))
