from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.crued.user import get_user_by_id, verify_token, check_user_exists, create_access_token, create_user, get_user_by_email
from backend.app.core.database import get_db
from backend.app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest, TokenResponse, UserProfile
from backend.app.utils.user import verify_password, parse_bearer_token
from backend.app.utils.user import hash_password
router = APIRouter()


@router.post('/register', response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing_user = await check_user_exists(payload.username, db)
    existing_email = await get_user_by_email(payload.email, db)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='用户已存在')
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='邮箱已被使用')


    user = await create_user(payload, db)
    token = await create_access_token(user.id, db)

    return TokenResponse(
        access_token=token,
        token_type='bearer',
        username=user.username,
        message='注册成功',
    )


@router.post('/login', response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await check_user_exists(payload.username, db)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='用户名或密码错误')
    token = await create_access_token(user.id, db)

    return TokenResponse(
        access_token=token,
        token_type='bearer',
        username=user.username,
        message='登录成功',
    )


@router.get('/profile', response_model=UserProfile)
async def get_profile(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    # 简单返回一个默认的用户信息；后续如果需要再接数据库或 token 校验
    token = parse_bearer_token(authorization)
    user_id = await verify_token(token, db)
    user = await get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='用户不存在')
    return UserProfile(
        id=user.id,
        username=user.username,
        email=user.email,
        message='用户资料获取成功',
    )


@router.post('/change-password')
async def change_password(
    payload: ChangePasswordRequest,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    token = parse_bearer_token(authorization)
    user_id = await verify_token(token, db)
    user = await get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='用户不存在')
    if user.username != payload.username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='无权修改其他用户的密码')
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='旧密码错误')
    
    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    # 不真正修改密码，只返回一个成功提示
    return {'message': f'用户 {payload.username} 的密码修改成功'}
