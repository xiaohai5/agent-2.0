from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from socket import timeout as SocketTimeout
from typing import AsyncIterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.chat import router as chat_router
from backend.app.api.routes.feedback import router as feedback_router
from backend.app.api.routes.vector_store import router as vector_router
from backend.app.core.database import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    yield


app = FastAPI(
    title="Agent 2.0 API",
    description="FastAPI backend for frontend integration demo.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "capacitor://localhost",
        "http://localhost",
        "http://175.27.169.218",
    ],
    allow_origin_regex=r"^(https?://.*|capacitor://.*|ionic://.*|file://.*)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(vector_router, prefix="/api/vector-store", tags=["vector-store"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(feedback_router, prefix="/api/feedback", tags=["feedback"])


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Agent 2.0 backend is running"}


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/image-proxy")
async def image_proxy(url: str = Query(..., min_length=1)) -> Response:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported image url")

    upstream_url = parsed._replace(scheme="http").geturl()

    def fetch_image() -> tuple[bytes, str]:
        request = UrlRequest(
            upstream_url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.amap.com/",
                "Connection": "close",
            },
        )
        with urlopen(request, timeout=5) as response:
            content_type = response.headers.get("Content-Type", "image/jpeg")
            if not content_type.startswith("image/"):
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream did not return an image")
            content_length = int(response.headers.get("Content-Length") or 0)
            if content_length > 5 * 1024 * 1024:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Image is too large")
            read_size = content_length or 5 * 1024 * 1024 + 1
            return response.read(read_size), content_type

    try:
        content, content_type = await asyncio.to_thread(fetch_image)
    except HTTPException:
        raise
    except (HTTPError, URLError, TimeoutError, SocketTimeout) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Image fetch failed: {exc}") from exc

    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Image is too large")

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Length": str(len(content)),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": str(exc.detail), "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    location = ".".join([str(item) for item in first_error.get("loc", []) if item != "body"])
    message = first_error.get("msg", "请求参数校验失败")
    detail = f"{location}: {message}" if location else message
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"code": 422, "message": detail, "data": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"code": 500, "message": "服务器内部错误，请稍后重试", "data": None},
    )
