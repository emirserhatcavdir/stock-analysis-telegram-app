"""Portfolio service shared by Telegram bot and FastAPI routes."""

from __future__ import annotations

from typing import Any

from apps.api.deps import load_portfolio


def get_portfolio(user_id: int) -> dict[str, Any]:
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


# POST endpoints are intentionally thin wrappers over the existing persistence helpers.
# The actual mutations live in stock_bot/data_manager.py so bot and API share storage.
def add_position(user_id: int, symbol: str, shares: float = 0, buy_price: float | None = None) -> dict[str, Any]:
    from data_manager import upsert_portfolio_entry
    from analysis import get_current_price, normalize_symbol

    normalized = normalize_symbol(symbol)
    current_price = get_current_price(normalized)
    final_price = buy_price if buy_price is not None else current_price
    entry = {
        "shares": float(shares),
        "buy_price": float(final_price or 0),
        "buy_date": None,
    }
    saved = upsert_portfolio_entry(user_id, normalized, entry)
    return {
        "ok": saved,
        "user_id": user_id,
        "symbol": normalized,
        "shares": float(shares),
        "buy_price": final_price,
        "message": "Position added" if saved else "Position could not be saved",
    }


def remove_position(user_id: int, symbol: str) -> dict[str, Any]:
    from data_manager import remove_portfolio_symbol
    from analysis import normalize_symbol

    normalized = normalize_symbol(symbol)
    saved, removed = remove_portfolio_symbol(user_id, normalized)
    return {
        "ok": saved and removed,
        "user_id": user_id,
        "symbol": normalized,
        "message": "Position removed" if saved and removed else "Position could not be removed",
    }
