"""Service functions that reuse bot analysis/scanning logic."""

from __future__ import annotations

from typing import Any

from apps.api.deps import (
    SCAN_UNIVERSES,
    analyze,
    get_chat_watchlist,
    load_portfolio,
    normalize_symbol,
    scan_top_stocks,
    score_analysis,
)


def get_portfolio_by_user(user_id: int) -> dict[str, Any]:
    raw = load_portfolio(user_id)
    positions: dict[str, dict[str, Any]] = {}
    for symbol, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        positions[symbol] = {
            "shares": float(entry.get("shares", 0) or 0),
            "buy_price": float(entry.get("buy_price", 0) or 0),
            "buy_date": entry.get("buy_date"),
            "realized_pnl": entry.get("realized_pnl"),
        }
    return {
        "user_id": user_id,
        "positions": positions,
        "total_positions": len(positions),
    }


def get_watchlist_by_user(user_id: int) -> dict[str, Any]:
    symbols = get_chat_watchlist(user_id)
    return {
        "user_id": user_id,
        "symbols": symbols,
        "count": len(symbols),
    }


def get_scan_results(limit: int = 10) -> dict[str, Any]:
    symbols = SCAN_UNIVERSES.get("bist30", [])
    ranked = scan_top_stocks(symbols, top_n=max(1, min(limit, 20)), max_symbols=30)
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(ranked, start=1):
        rows.append(
            {
                "rank": idx,
                "symbol": row.symbol,
                "score": row.score,
                "signal": row.signal,
                "strength": row.strength,
            }
        )
    return {
        "universe": "bist30",
        "count": len(rows),
        "results": rows,
    }


def get_symbol_details(ticker: str) -> dict[str, Any] | None:
    symbol = normalize_symbol(ticker)
    result = analyze(symbol)
    if result is None:
        return None

    scored = score_analysis(result)
    return {
        "symbol": symbol,
        "price": result.price,
        "change_pct": result.change_pct,
        "rsi": result.rsi,
        "ma20": result.ma20,
        "ma50": result.ma50,
        "ma200": result.ma200,
        "macd": result.macd,
        "signal": result.macd_signal,
        "histogram": result.macd_hist,
        "bb_upper": result.bb_upper,
        "bb_middle": result.bb_mid,
        "bb_lower": result.bb_lower,
        "trend": result.trend,
        "score": scored.score,
        "score_strength": scored.strength,
        "summary": result.signal_summary,
    }

