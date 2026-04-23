from project_config import SETTINGS
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine
from backend.app.models import Base

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
    # 导入所有模型以确保它们被注册
    from backend.app.models.feedback import MessageFeedback
    from backend.app.models.graphrag import GraphEntity, GraphRelationship, GraphSemanticChunk
    from backend.app.models.user import User
    from backend.app.models.user_memory import UserMemory
    from backend.app.models.vector_store import UploadResponse, DocumentItem

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_documents_columns(conn)


async def _ensure_documents_columns(conn) -> None:
    """Add columns needed by document uploads to older local schemas."""

    def get_columns(sync_conn) -> set[str]:
        inspector = inspect(sync_conn)
        if not inspector.has_table("documents"):
            return set()
        return {column["name"] for column in inspector.get_columns("documents")}

    existing_columns = await conn.run_sync(get_columns)
    required_columns = {
        "file_path": "ADD COLUMN file_path VARCHAR(500) NOT NULL DEFAULT ''",
        "text_path": "ADD COLUMN text_path VARCHAR(500) NOT NULL DEFAULT ''",
        "status": "ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'recorded'",
        "updated_at": "ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }

    for column_name, ddl in required_columns.items():
        if column_name not in existing_columns:
            await conn.execute(text(f"ALTER TABLE documents {ddl}"))
