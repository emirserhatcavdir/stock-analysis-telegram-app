"""Shared scan/rank service for the dashboard API."""

from __future__ import annotations

import logging
import math
from typing import Any

from deps import (
    SCAN_UNIVERSES,
    add_chat_watch_symbol,
    analyze,
    normalize_symbol,
    scan_top_stocks,
    score_analysis,
)
from services.analysis_service import get_analysis as _get_analysis

logger = logging.getLogger(__name__)


def _get_value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _to_finite_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(numeric):
        return default
    return numeric


def _sanitize_scan_row(row: dict[str, Any]) -> dict[str, Any] | None:
    symbol = str(row.get("symbol") or "").strip()
    if not symbol:
        return None

    score = _to_int(row.get("score"), default=0)
    signal = str(row.get("signal") or "neutral").strip() or "neutral"
    strength = str(row.get("strength") or "balanced").strip() or "balanced"
    trend = str(row.get("trend") or "Trend n/a").strip() or "Trend n/a"
    summary = str(row.get("summary") or "").strip() or None

    tags_raw = row.get("tags")
    if isinstance(tags_raw, list):
        tags = [str(tag).strip() for tag in tags_raw if str(tag).strip()]
    else:
        tags = []

    return {
        "symbol": symbol,
        "score": max(0, min(100, score)),
        "signal": signal,
        "strength": strength,
        "rsi": _to_finite_float(row.get("rsi"), None),
        "trend": trend,
        "summary": summary,
        "ma20": _to_finite_float(row.get("ma20"), None),
        "ma50": _to_finite_float(row.get("ma50"), None),
        "ma200": _to_finite_float(row.get("ma200"), None),
        "macd": _to_finite_float(row.get("macd"), None),
        "macd_signal": _to_finite_float(row.get("macd_signal"), None),
        "macd_hist": _to_finite_float(row.get("macd_hist"), None),
        "price": _to_finite_float(row.get("price"), None),
        "bb_upper": _to_finite_float(row.get("bb_upper"), None),
        "bb_lower": _to_finite_float(row.get("bb_lower"), None),
        "tags": tags[:5],
    }


def _is_strong_buy(signal: str, strength: str) -> bool:
    normalized_signal = str(signal or "").strip().lower().replace(" ", "_")
    normalized_strength = str(strength or "").strip().lower().replace(" ", "_")
    return normalized_signal in {"strong_buy", "buy"} and normalized_strength in {
        "strong",
        "strong_buy",
        "strongbuy",
        "strong buy",
    }


def _build_opportunity_tags(row: dict[str, Any]) -> list[str]:
    score = _to_int(row.get("score"), default=0)
    signal = str(row.get("signal") or "").strip().lower().replace(" ", "_")
    strength = str(row.get("strength") or "").strip().lower().replace(" ", "_")
    rsi = row.get("rsi")
    trend = str(row.get("trend") or "").strip().lower()
    ma20 = row.get("ma20")
    ma50 = row.get("ma50")
    ma200 = row.get("ma200")
    macd = row.get("macd")
    macd_signal = row.get("macd_signal")
    macd_hist = row.get("macd_hist")
    price = row.get("price")
    bb_upper = row.get("bb_upper")
    bb_lower = row.get("bb_lower")

    tags: list[str] = []

    bullish_alignment = (
        isinstance(price, (int, float))
        and isinstance(ma20, (int, float))
        and isinstance(ma50, (int, float))
        and isinstance(ma200, (int, float))
        and price > ma200
        and ma20 > ma50 > ma200
    )
    bearish_alignment = (
        isinstance(price, (int, float))
        and isinstance(ma20, (int, float))
        and isinstance(ma50, (int, float))
        and isinstance(ma200, (int, float))
        and price < ma200
        and ma20 < ma50 < ma200
    )
    bullish_macd = isinstance(macd, (int, float)) and isinstance(macd_signal, (int, float)) and macd > macd_signal and (macd_hist is None or macd_hist >= 0)
    bearish_macd = isinstance(macd, (int, float)) and isinstance(macd_signal, (int, float)) and macd < macd_signal and (macd_hist is None or macd_hist <= 0)
    breakout = (
        isinstance(price, (int, float))
        and isinstance(bb_upper, (int, float))
        and price >= bb_upper
        and score >= 55
    )
    oversold_rebound = (
        isinstance(rsi, (int, float))
        and rsi <= 35
        and score >= 45
        and not bearish_alignment
    )
    weak_risky = (
        score < 45
        or bearish_alignment
        or bearish_macd
        or (isinstance(rsi, (int, float)) and rsi >= 70)
    )

    if score >= 65 and (bullish_alignment or trend.startswith("📈")):
        tags.append("Trend Leader")
    if bullish_macd and score >= 55:
        tags.append("Momentum")
    if oversold_rebound:
        tags.append("Oversold Rebound")
    if breakout:
        tags.append("Breakout Candidate")
    if weak_risky:
        tags.append("Weak / Risky")

    if not tags:
        if score >= 55:
            tags.append("Momentum")
        elif score >= 45:
            tags.append("Trend Leader")
        else:
            tags.append("Weak / Risky")

    if strength in {"strong", "moderate"} and score >= 60 and "Trend Leader" not in tags and bullish_alignment:
        tags.insert(0, "Trend Leader")

    seen: set[str] = set()
    unique_tags: list[str] = []
    for tag in tags:
        if tag in seen:
            continue
        seen.add(tag)
        unique_tags.append(tag)
    return unique_tags[:3]


def _resolve_symbol_row(raw_row: Any) -> dict[str, Any] | None:
    symbol = str(_get_value(raw_row, "symbol", "")).strip()
    if not symbol:
        return None

    normalized_symbol = normalize_symbol(symbol)
    try:
        result = analyze(normalized_symbol)
    except Exception as exc:
        logger.warning("_resolve_symbol_row: analyze failed for symbol=%s error=%s", normalized_symbol, exc)
        return None
    if result is None:
        logger.debug("_resolve_symbol_row: no analysis for symbol=%s", normalized_symbol)
        return None

    scored = score_analysis(result)
    row_score = _to_int(_get_value(raw_row, "score", scored.score), default=int(scored.score))
    row_signal = str(_get_value(raw_row, "signal", getattr(scored, "signal", result.score_signal)) or "").strip()
    row_strength = str(_get_value(raw_row, "strength", scored.strength) or "").strip()
    row_ma20 = _get_value(raw_row, "ma20", result.ma20)
    row_ma50 = _get_value(raw_row, "ma50", result.ma50)
    row_ma200 = _get_value(raw_row, "ma200", result.ma200)
    row_macd = _get_value(raw_row, "macd", result.macd)
    row_macd_signal = _get_value(raw_row, "macd_signal", result.macd_signal)
    row_macd_hist = _get_value(raw_row, "macd_hist", result.macd_hist)
    row_price = _get_value(raw_row, "price", result.price)
    row_bb_upper = _get_value(raw_row, "bb_upper", result.bb_upper)
    row_bb_lower = _get_value(raw_row, "bb_lower", result.bb_lower)

    row = {
        "symbol": normalized_symbol,
        "score": row_score,
        "signal": row_signal or result.score_signal,
        "strength": row_strength or scored.strength,
        "rsi": result.rsi,
        "ma20": row_ma20,
        "ma50": row_ma50,
        "ma200": row_ma200,
        "macd": row_macd,
        "macd_signal": row_macd_signal,
        "macd_hist": row_macd_hist,
        "price": row_price,
        "bb_upper": row_bb_upper,
        "bb_lower": row_bb_lower,
        "trend": result.trend,
        "summary": result.signal_summary,
    }
    row["tags"] = _build_opportunity_tags(row)
    return _sanitize_scan_row(row)


def normalize_scan_rows(
    raw_rows: list[Any],
    *,
    min_score: int | None = None,
    strong_buy_only: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for raw_row in raw_rows:
        try:
            row = _resolve_symbol_row(raw_row)
        except Exception as exc:
            logger.warning(
                "normalize_scan_rows: failed to resolve symbol row for symbol=%s error=%s",
                _get_value(raw_row, "symbol", "unknown"),
                exc,
            )
            continue
        if row is None:
            continue

        if min_score is not None and row["score"] < min_score:
            continue
        if strong_buy_only and not _is_strong_buy(row["signal"], row["strength"]):
            continue

        rows.append(row)

    for index, row in enumerate(rows, start=1):
        row["rank"] = index

    return rows


def _build_scan_payload(
    universe: str = "bist30",
    *,
    limit: int = 10,
    min_score: int | None = None,
    strong_buy_only: bool = False,
) -> dict[str, Any] | None:
    requested_universe = str(universe or "").strip().lower()
    universe_aliases = {
        "all": "bist30",
        "bist50": "bist30",
        "bist100": "bist30",
    }
    resolved_universe = requested_universe
    if requested_universe not in SCAN_UNIVERSES:
        resolved_universe = universe_aliases.get(requested_universe, "bist30")

    symbols = SCAN_UNIVERSES.get(resolved_universe, [])
    if not symbols:
        logger.warning("run_scan: universe=%s resolved to empty symbol list", resolved_universe)
        return {
            "universe": resolved_universe,
            "count": 0,
            "results": [],
        }

    top_n = max(1, min(limit, 20))
    try:
        raw_rows = scan_top_stocks(symbols, top_n=top_n, max_symbols=30)
    except Exception:
        logger.exception(
            "run_scan: scan_top_stocks failed universe=%s limit=%s min_score=%s strong_buy_only=%s",
            resolved_universe,
            limit,
            min_score,
            strong_buy_only,
        )
        raw_rows = []

    if not isinstance(raw_rows, list):
        logger.error("run_scan: scan_top_stocks returned non-list type=%s", type(raw_rows).__name__)
        raw_rows = []

    rows = normalize_scan_rows(
        raw_rows,
        min_score=min_score,
        strong_buy_only=strong_buy_only,
    )

    return {
        "universe": resolved_universe,
        "count": len(rows),
        "results": rows[:limit],
    }


def run_scan(
    universe: str = "bist30",
    limit: int = 10,
    min_score: int | None = None,
    strong_buy_only: bool = False,
) -> dict[str, Any] | None:
    return _build_scan_payload(
        universe,
        limit=limit,
        min_score=min_score,
        strong_buy_only=strong_buy_only,
    )


def rank_symbols(
    universe: str = "bist30",
    limit: int = 10,
    min_score: int | None = None,
) -> dict[str, Any] | None:
    return _build_scan_payload(
        universe,
        limit=limit,
        min_score=min_score,
        strong_buy_only=False,
    )


def get_analysis(symbol: str, period: str = "1y") -> dict[str, Any] | None:
    return _get_analysis(symbol, period=period)


def add_symbol_to_watchlist(user_id: int, symbol: str) -> dict[str, Any]:
    normalized = normalize_symbol(symbol)
    saved, added = add_chat_watch_symbol(user_id, normalized)
    return {
        "ok": saved and added,
        "user_id": user_id,
        "symbol": normalized,
        "message": "Symbol added" if saved and added else "Symbol already exists or could not be saved",
    }


def get_symbol_score(symbol: str) -> dict[str, Any] | None:
    """Get comprehensive score and analysis for a single symbol."""
    normalized = normalize_symbol(symbol)
    result = analyze(normalized)
    if result is None:
        return None

    scored = score_analysis(result)
    return {
        "symbol": normalized,
        "score": _to_int(scored.score),
        "signal": scored.signal,
        "strength": scored.strength,
        "rsi": result.rsi,
        "ma20": result.ma20,
        "ma50": result.ma50,
        "ma200": result.ma200,
        "trend": result.trend,
        "ma_note": result.ma_availability_note,
        "summary": result.signal_summary,
    }

