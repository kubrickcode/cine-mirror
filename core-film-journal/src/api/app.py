"""FastAPI 앱 생성 및 라우터 등록."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="core-film-journal")


@app.get("/api/health")
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok"})
