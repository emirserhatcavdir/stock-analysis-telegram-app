"""Dependency and import helpers for API layer."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
STOCK_BOT_DIR = ROOT_DIR / "stock_bot"
if str(STOCK_BOT_DIR) not in sys.path:
    sys.path.insert(0, str(STOCK_BOT_DIR))

from analysis import analyze, normalize_symbol  # noqa: E402
from data_manager import add_chat_watch_symbol, get_chat_watchlist, load_portfolio, load_watch_store  # noqa: E402
from scanner import SCAN_UNIVERSES, run_scan  # noqa: E402
from scoring import scan_top_stocks, score_analysis, score_symbol  # noqa: E402

__all__ = [
    "add_chat_watch_symbol",
    "get_chat_watchlist",
    "analyze",
    "load_portfolio",
    "load_watch_store",
    "normalize_symbol",
    "run_scan",
    "score_analysis",
    "score_symbol",
    "scan_top_stocks",
    "SCAN_UNIVERSES",
]
