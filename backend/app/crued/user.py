from datetime import datetime, timedelta

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.models.user import User, UserToken
from backend.app.schemas.auth import RegisterRequest
from backend.app.utils.user import hash_password
import uuid
from fastapi import HTTPException, status

async def check_user_exists(username: str, db: AsyncSession = Depends(get_db)) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_username(username: str, db: AsyncSession = Depends(get_db)) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_email(email: str, db: AsyncSession = Depends(get_db)) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(data: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    password_hash = hash_password(data.password)
    user = User(
        username=data.username,
        email=data.email,
        password_hash=password_hash,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_access_token(user_id: int, db: AsyncSession = Depends(get_db), expires_days: int = 7) -> str:
    token = str(uuid.uuid4())
    result = await db.execute(select(UserToken).where(UserToken.user_id == user_id))
    user_token = result.scalar_one_or_none()

    if user_token:
        user_token.token = token
        user_token.expires_at = datetime.now() + timedelta(days=expires_days)
        db.add(user_token)
        await db.commit()
        await db.refresh(user_token)
        return user_token.token

    user_token = UserToken(
        user_id=user_id,
        token=token,
        expires_at=datetime.now() + timedelta(days=expires_days),
    )
    db.add(user_token)
    await db.commit()
    await db.refresh(user_token)
    return user_token.token


async def verify_token(token: str, db: AsyncSession = Depends(get_db)) -> User:
    result = await db.execute(select(UserToken).where(UserToken.token == token))
    user_token = result.scalar_one_or_none()
    # 先判断是否存在，再判断是否过期，避免 user_token 为 None 时访问其属性
    if not user_token or user_token.expires_at < datetime.now():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='token 已过期')
    return user_token.user_id

async def get_user_by_id(user_id: int, db: AsyncSession = Depends(get_db)) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

