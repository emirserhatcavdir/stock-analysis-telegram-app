"""Public API endpoints with clean path structure for Mini App/backend clients."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from apps.api.schemas import ScanResponse, SymbolResponse, UserPortfolioResponse, UserWatchlistResponse
from apps.api.services.market_service import (
    get_portfolio_by_user,
    get_scan_results,
    get_symbol_details,
    get_watchlist_by_user,
)

router = APIRouter(tags=["public"])


@router.get("/portfolio/{user_id}", response_model=UserPortfolioResponse)
def portfolio_by_user(user_id: int) -> UserPortfolioResponse:
    data = get_portfolio_by_user(user_id)
    return UserPortfolioResponse(**data)


@router.get("/watchlist/{user_id}", response_model=UserWatchlistResponse)
def watchlist_by_user(user_id: int) -> UserWatchlistResponse:
    data = get_watchlist_by_user(user_id)
    return UserWatchlistResponse(**data)


@router.get("/scan", response_model=ScanResponse)
def scan(limit: int = Query(default=10, ge=1, le=20)) -> ScanResponse:
    data = get_scan_results(limit=limit)
    return ScanResponse(**data)


@router.get("/symbol/{ticker}", response_model=SymbolResponse)
def symbol(ticker: str) -> SymbolResponse:
    data = get_symbol_details(ticker)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No data for symbol: {ticker}")
    return SymbolResponse(**data)

