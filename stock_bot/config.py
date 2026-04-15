"""Centralized configuration for the stock bot."""

from __future__ import annotations

import os
from pathlib import Path

# ── Telegram ──────────────────────────────────────────────────
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
MINI_APP_URL = os.getenv("TELEGRAM_MINI_APP_URL", "https://madge-nonanarchic-fleetingly.ngrok-free.dev").strip()


# ── File paths ────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)

PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
ALERTS_FILE = DATA_DIR / "alerts.json"
RSI_STATE_FILE = DATA_DIR / "rsi_state.json"
WATCHLIST_FILE = DATA_DIR / "watchlist.json"
TRADES_FILE = DATA_DIR / "trades.json"

# ── Alert timing ──────────────────────────────────────────────
ALERT_INTERVAL_SECONDS = 900  # 15 minutes

# ── Technical analysis thresholds ─────────────────────────────
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0

MA_SHORT = 20
MA_MID = 50
MA_LONG = 200

# ── Chart defaults ────────────────────────────────────────────
CHART_PERIOD = "6mo"
CHART_DPI = 100
