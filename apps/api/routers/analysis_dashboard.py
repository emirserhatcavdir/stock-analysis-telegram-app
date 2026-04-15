"""Dashboard-facing analysis and chart endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from apps.api.schemas import AnalysisResponse, ChartResponse, ChartSeriesResponse, ScoreResponse, SymbolResponse
from apps.api.services.analysis_service import get_analysis, get_symbol_chart, get_symbol_chart_series, get_symbol_details
from apps.api.services.scan_service import get_symbol_score

router = APIRouter(tags=["analysis"])


def _ma_alignment(ma20: float | None, ma50: float | None, ma200: float | None) -> str:
    if ma20 is None or ma50 is None or ma200 is None:
        return "unknown"
    if ma20 > ma50 > ma200:
        return "bullish"
    if ma20 < ma50 < ma200:
        return "bearish"
    return "mixed"


@router.get("/symbol/{ticker}", response_model=SymbolResponse)
def symbol(ticker: str) -> SymbolResponse:
    data = get_symbol_details(ticker)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No data for symbol: {ticker}")
    return SymbolResponse(**data)


@router.get("/symbol/{ticker}/chart")
def symbol_chart(ticker: str) -> Response:
    png = get_symbol_chart(ticker)
    if png is None:
        raise HTTPException(status_code=404, detail=f"No chart for symbol: {ticker}")
    return Response(content=png, media_type="image/png")


@router.get("/symbol/{ticker}/chart-series", response_model=ChartSeriesResponse)
def symbol_chart_series(
    ticker: str,
    period: str = Query(default="6mo", pattern="^(1mo|3mo|6mo|1y|2y)$"),
    limit: int = Query(default=240, ge=30, le=600),
) -> ChartSeriesResponse:
    series = get_symbol_chart_series(ticker, period=period, limit=limit)
    if series is None:
        raise HTTPException(status_code=404, detail=f"No chart data for symbol: {ticker}")
    return ChartSeriesResponse(**series)


@router.get("/analysis/{symbol}", response_model=AnalysisResponse)
def analysis(
    symbol: str,
    period: str = Query(default="1y", pattern="^(1mo|3mo|6mo|1y|2y)$"),
) -> AnalysisResponse:
    data = get_analysis(symbol, period=period)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No data for symbol: {symbol}")
    return AnalysisResponse(**data)


@router.get("/score/{symbol}", response_model=ScoreResponse)
def score(symbol: str) -> ScoreResponse:
    data = get_symbol_score(symbol)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No data for symbol: {symbol}")
    return ScoreResponse(
        symbol=data["symbol"],
        score=data["score"],
        strength=data["strength"],
        rsi=data.get("rsi"),
        ma20=data.get("ma20"),
        ma50=data.get("ma50"),
        ma200=data.get("ma200"),
        ma_note=data.get("ma_note"),
        trend=data["trend"],
        ma_alignment=_ma_alignment(data.get("ma20"), data.get("ma50"), data.get("ma200")),
        summary=data["summary"],
    )

