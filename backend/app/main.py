from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.chat import router as chat_router
from backend.app.api.routes.vector_store import router as vector_router
from backend.app.core.database import init_db
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
app = FastAPI(
    title='RAG Project API',
    description='FastAPI backend interfaces for auth, document registry, and chat.',
    version='0.1.0',
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth_router, prefix='/api/auth', tags=['auth'])
app.include_router(vector_router, prefix='/api/vector-store', tags=['vector-store'])
app.include_router(chat_router, prefix='/api/chat', tags=['chat'])


@app.get('/')
async def root() -> dict[str, str]:
    return {'message': 'RAG backend is running'}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={'detail': '服务器内部错误，请稍后重试'},
    )
