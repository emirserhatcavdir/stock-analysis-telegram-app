"""Watchlist service shared by Telegram bot and FastAPI routes."""

from __future__ import annotations

from typing import Any

from deps import get_chat_watchlist


def get_watchlist(user_id: int) -> dict[str, Any]:
    symbols = get_chat_watchlist(user_id)
    return {
        "user_id": user_id,
        "symbols": symbols,
        "count": len(symbols),
    }


def add_symbol(user_id: int, symbol: str) -> dict[str, Any]:
    from analysis import normalize_symbol
    from data_manager import add_chat_watch_symbol

    normalized = normalize_symbol(symbol)
    saved, added = add_chat_watch_symbol(user_id, normalized)
    return {
        "ok": saved and added,
        "user_id": user_id,
        "symbol": normalized,
        "message": "Symbol added" if saved and added else "Symbol already exists or could not be saved",
    }


def remove_symbol(user_id: int, symbol: str) -> dict[str, Any]:
    from analysis import normalize_symbol
    from data_manager import remove_chat_watch_symbol

    normalized = normalize_symbol(symbol)
    saved, removed = remove_chat_watch_symbol(user_id, normalized)
    return {
        "ok": saved and removed,
        "user_id": user_id,
        "symbol": normalized,
        "message": "Symbol removed" if saved and removed else "Symbol could not be removed",
    }

