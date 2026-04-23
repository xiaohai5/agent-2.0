"""
认证服务 - 使用 MySQL 数据库
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.crued import user as user_crud
from backend.app.utils.user import hash_password, verify_password


class AuthService:
    async def register(self, db: AsyncSession, username: str, email: str, password: str) -> dict:
        """用户注册"""
        try:
            user = await user_crud.create_user(db, username=username, email=email, password_hash=hash_password(password))
            await db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        token = await user_crud.issue_token(db, user.id)
        await db.commit()

        return {
            "access_token": token,
            "token_type": "bearer",
            "username": user.username,
        }

    async def login(self, db: AsyncSession, username: str, password: str) -> dict:
        """用户登录"""
        user = await user_crud.find_user_by_username(db, username)
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

        token = await user_crud.issue_token(db, user.id)
        await db.commit()

        return {
            "access_token": token,
            "token_type": "bearer",
            "username": user.username,
        }

    async def get_profile(self, db: AsyncSession, user_id: int) -> dict:
        """获取用户资料"""
        user = await user_crud.find_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效")

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }

    async def change_password(
        self,
        db: AsyncSession,
        user_id: int,
        username: str,
        old_password: str,
        new_password: str,
        confirm_password: str,
    ) -> None:
        """修改密码"""
        user = await user_crud.find_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效")

        if user.username != username:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只允许修改当前登录用户的密码")

        if new_password != confirm_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="两次输入的新密码不一致")

        if not verify_password(old_password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="旧密码不正确")

        await user_crud.update_user_password(db, user_id=user_id, password_hash=hash_password(new_password))
        await db.commit()


auth_service = AuthService()
