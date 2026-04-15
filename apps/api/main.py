"""Phase 1 FastAPI app skeleton."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routers.alerts_dashboard import router as alerts_dashboard_router
from apps.api.routers.analysis import router as analysis_router
from apps.api.routers.analysis_dashboard import router as analysis_dashboard_router
from apps.api.routers.portfolio import router as portfolio_router
from apps.api.routers.portfolio_dashboard import router as portfolio_dashboard_router
from apps.api.routers.public import router as public_router
from apps.api.routers.scan_dashboard import router as scan_dashboard_router
from apps.api.routers.watchlist import router as watchlist_router
from apps.api.routers.watchlist_dashboard import router as watchlist_dashboard_router


def _cors_origins_from_env() -> list[str]:
    raw = os.getenv("FRONTEND_ORIGINS", "").strip()
    env_origins = [item.strip() for item in raw.split(",") if item.strip()]

    prod_origin = os.getenv("VERCEL_PROD_ORIGIN", "").strip()
    preview_origin = os.getenv("VERCEL_PREVIEW_ORIGIN", "").strip()

    defaults = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    merged = defaults + env_origins + [prod_origin, preview_origin]
    unique: list[str] = []
    for origin in merged:
        if origin and origin not in unique:
            unique.append(origin)
    return unique


def _cors_allow_all_debug() -> bool:
    value = os.getenv("CORS_ALLOW_ALL", "").strip().lower()
    return value in {"1", "true", "yes", "on"}

app = FastAPI(title="BIST Bot API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https://stock-analysis-telegram-.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(analysis_router)
app.include_router(analysis_dashboard_router)
app.include_router(portfolio_router)
app.include_router(portfolio_dashboard_router)
app.include_router(watchlist_router)
app.include_router(watchlist_dashboard_router)
app.include_router(scan_dashboard_router)
app.include_router(alerts_dashboard_router)
app.include_router(public_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

