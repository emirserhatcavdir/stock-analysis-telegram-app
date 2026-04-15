"""Dashboard-facing scan and rank endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from apps.api.schemas import AnalysisResponse, MutationResponse, ScanResponse, WatchlistAddRequest
from apps.api.services.scan_service import add_symbol_to_watchlist, get_analysis, rank_symbols, run_scan

router = APIRouter(tags=["scan"])


@router.get("/scan", response_model=ScanResponse)
@router.get("/api/scan", response_model=ScanResponse)
def scan(
    universe: str = Query(default="bist30"),
    limit: int = Query(default=10, ge=1, le=20),
    min_score: int | None = Query(default=None, ge=0, le=100),
    strong_buy_only: bool = Query(default=False),
) -> ScanResponse:
    data = run_scan(
        universe=universe,
        limit=limit,
        min_score=min_score,
        strong_buy_only=strong_buy_only,
    )
    if data is None:
        raise HTTPException(status_code=500, detail="Scan failed")
    return ScanResponse(**data)


@router.get("/rank", response_model=ScanResponse)
def rank(
    universe: str = Query(default="bist30"),
    limit: int = Query(default=10, ge=1, le=20),
    min_score: int | None = Query(default=None, ge=0, le=100),
) -> ScanResponse:
    data = rank_symbols(
        universe=universe,
        limit=limit,
        min_score=min_score,
    )
    if data is None:
        raise HTTPException(status_code=500, detail="Rank failed")
    return ScanResponse(**data)


@router.get("/analysis/{symbol}", response_model=AnalysisResponse)
def analysis(
    symbol: str,
    period: str = Query(default="1y", pattern="^(1mo|3mo|6mo|1y|2y)$"),
) -> AnalysisResponse:
    data = get_analysis(symbol, period=period)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No data for symbol: {symbol}")
    return AnalysisResponse(**data)


@router.post("/watchlist/{user_id}/add", response_model=MutationResponse)
def watchlist_add(user_id: int, payload: WatchlistAddRequest) -> MutationResponse:
    data = add_symbol_to_watchlist(user_id, payload.symbol)
    if not data["ok"]:
        raise HTTPException(status_code=400, detail=data["message"])
    return MutationResponse(ok=True, message=data["message"], user_id=user_id)

