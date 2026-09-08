from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import albums, families, photos, system, trips
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(
    title="オモイデ工房 API",
    description="思い出カラー化×巡礼旅エージェント（Cloud Run: api / agent）",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    families.router,
    albums.router,
    photos.router,
    trips.router,
    system.router,
):
    app.include_router(router, prefix="/api")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "env": settings.app_env, "gemini": settings.gemini_mode}


# 本番用の 1 コンテナ構成（Dockerfile.deploy）ではビルド済み PWA を同居させる。
# 開発時（docker compose）は Vite が配信するのでこのブロックは無効。
_STATIC = Path("/app/static")
if (_STATIC / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_STATIC / "assets"), name="assets")

    @app.get("/{path:path}")
    async def spa(path: str) -> FileResponse:
        candidate = _STATIC / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        if path.startswith("api/"):
            raise HTTPException(404, "見つかりません")
        return FileResponse(_STATIC / "index.html")
