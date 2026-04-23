"""
依赖注入 - 获取当前用户
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.crued import user as user_crud
from backend.app.utils.user import parse_bearer_token


async def get_current_user_id(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> int:
    """从 Authorization header 中获取当前用户 ID"""
    token = parse_bearer_token(authorization)

    user = await user_crud.verify_token(db, token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效，请重新登录")

    return user.id
