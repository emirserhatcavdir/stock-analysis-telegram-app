"""Read-only analysis endpoints for Phase 2."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from fastapi import APIRouter, HTTPException, Query

from apps.api.deps import analyze, normalize_symbol, run_scan, score_analysis
from apps.api.schemas import AnalysisResponse, ScanBist30Response, ScanItem, ScoreResponse

router = APIRouter(prefix="/api", tags=["analysis"])
logger = logging.getLogger(__name__)


def _ma_alignment(ma20: float | None, ma50: float | None, ma200: float | None) -> str:
    if ma20 is None or ma50 is None or ma200 is None:
        return "unknown"
    if ma20 > ma50 > ma200:
        return "bullish"
    if ma20 < ma50 < ma200:
        return "bearish"
    return "mixed"


def _scan_item(result) -> ScanItem:
    def _safe_float(value):
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    symbol = str(getattr(result, "symbol", "") or "").strip()
    if not symbol:
        symbol = "UNKNOWN"

    trend = str(getattr(result, "trend", "") or "").strip() or "n/a"

    return ScanItem(
        symbol=symbol,
        rsi=_safe_float(getattr(result, "rsi", None)),
        change_pct=_safe_float(getattr(result, "change_pct", None)),
        price=_safe_float(getattr(result, "price", None)),
        trend=trend,
    )


@router.get("/score/{symbol}", response_model=ScoreResponse)
def get_score(symbol: str) -> ScoreResponse:
    normalized = normalize_symbol(symbol)
    result = analyze(normalized)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No data for symbol: {normalized}")
    scored = score_analysis(result)

    return ScoreResponse(
        symbol=normalized,
        score=scored.score,
        strength=scored.strength,
        rsi=result.rsi,
        ma20=result.ma20,
        ma50=result.ma50,
        ma200=result.ma200,
        ma_note=result.ma_availability_note,
        trend=result.trend,
        ma_alignment=_ma_alignment(result.ma20, result.ma50, result.ma200),
        summary=result.signal_summary,
    )


@router.get("/scan/bist30", response_model=ScanBist30Response)
def get_scan_bist30() -> ScanBist30Response:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run_scan, "bist30")
        try:
            report = future.result(timeout=90)
        except TimeoutError as exc:
            logger.exception("/api/scan/bist30 timed out")
            raise HTTPException(status_code=504, detail="Scan timed out") from exc
        except Exception:
            logger.exception("/api/scan/bist30 failed while building scan report")
            report = None
    if report is None:
        return ScanBist30Response(
            universe="bist30",
            analyzed_count=0,
            failed_count=0,
            oversold=[],
            overbought=[],
            strong_trend=[],
        )

    def _safe_scan_items(items, bucket_name: str):
        safe_items = []
        for item in items or []:
            try:
                safe_items.append(_scan_item(item))
            except Exception:
                logger.exception("/api/scan/bist30 skipped malformed item in %s", bucket_name)
        return safe_items

    return ScanBist30Response(
        universe=str(getattr(report, "universe", "bist30") or "bist30"),
        analyzed_count=int(getattr(report, "analyzed_count", 0) or 0),
        failed_count=int(getattr(report, "failed_count", 0) or 0),
        oversold=_safe_scan_items(getattr(report, "oversold", []), "oversold"),
        overbought=_safe_scan_items(getattr(report, "overbought", []), "overbought"),
        strong_trend=_safe_scan_items(getattr(report, "strongest_trend", []), "strong_trend"),
    )


@router.get("/analysis/{symbol}", response_model=AnalysisResponse)
def get_analysis(
    symbol: str,
    period: str = Query(default="1y", pattern="^(1mo|3mo|6mo|1y|2y)$"),
) -> AnalysisResponse:
    normalized = normalize_symbol(symbol)
    result = analyze(normalized, period=period)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No data for symbol: {normalized}")

    return AnalysisResponse(
        symbol=normalized,
        rsi=result.rsi,
        ma20=result.ma20,
        ma50=result.ma50,
        ma200=result.ma200,
        ma_note=result.ma_availability_note,
        trend=result.trend,
        commentary=result.commentary,
        signal_summary=result.signal_summary,
    )
