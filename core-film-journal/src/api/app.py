"""FastAPI 앱 생성 및 라우터 등록."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

import src.events.consumer  # noqa: F401 — 구독자 등록을 위한 import
from src.api.routers import journal, search
from src.events.broker import broker


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastStream 브로커 시작/종료 관리."""
    await broker.start()
    yield
    await broker.close()


app = FastAPI(title="core-film-journal", lifespan=_lifespan)

app.include_router(search.router)
app.include_router(journal.router)


@app.get("/api/health")
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok"})
