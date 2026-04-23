"""
用户相关的数据库 CRUD 操作
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import User, UserToken


TOKEN_EXPIRE_DAYS = 7


def utc_now() -> datetime:
    """返回当前 UTC 时间（naive datetime，与数据库一致）"""
    return datetime.utcnow()


async def create_user(db: AsyncSession, username: str, email: str, password_hash: str) -> User:
    """创建用户"""
    # 检查用户名是否存在
    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none():
        raise ValueError("用户名已存在")

    # 检查邮箱是否存在
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise ValueError("邮箱已被使用")

    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        created_at=utc_now()
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def find_user_by_username(db: AsyncSession, username: str) -> User | None:
    """根据用户名查找用户"""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def find_user_by_email(db: AsyncSession, email: str) -> User | None:
    """根据邮箱查找用户"""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def find_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """根据 ID 查找用户"""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def update_user_password(db: AsyncSession, user_id: int, password_hash: str) -> None:
    """更新用户密码"""
    user = await find_user_by_id(db, user_id)
    if not user:
        raise ValueError("用户不存在")

    user.password_hash = password_hash
    await db.flush()


async def issue_token(db: AsyncSession, user_id: int) -> str:
    """为用户颁发令牌"""
    # 删除该用户的旧令牌
    old_tokens = (await db.execute(select(UserToken).where(UserToken.user_id == user_id))).scalars().all()
    for token in old_tokens:
        await db.delete(token)

    # 创建新令牌
    token = str(uuid.uuid4())
    expires_at = utc_now() + timedelta(days=TOKEN_EXPIRE_DAYS)

    user_token = UserToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
        created_at=utc_now()
    )
    db.add(user_token)
    await db.flush()

    return token


async def verify_token(db: AsyncSession, token: str) -> User | None:
    """验证令牌并返回用户"""
    result = await db.execute(select(UserToken).where(UserToken.token == token))
    user_token = result.scalar_one_or_none()

    if not user_token:
        return None

    # 检查是否过期（使用 naive datetime 比较）
    if user_token.expires_at < utc_now():
        return None

    # 返回用户
    return await find_user_by_id(db, user_token.user_id)
