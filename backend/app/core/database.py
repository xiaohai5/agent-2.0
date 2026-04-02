from project_config import SETTINGS
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine
from backend.app.models.user import User
from backend.app.models.travel_plan import TravelPlan, TravelPlanLockedItem
from backend.app.models.vector_store import Base

ASYNC_DATABASE_URL = SETTINGS.async_database_url

# 创建异步引擎
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=True,  # 可选：输出SQL日志
    pool_size=10,  # 设置连接池中保持的持久连接数
    max_overflow=20,  # 设置连接池允许创建的额外连接数
)


# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# 依赖项，用于获取数据库会话
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
