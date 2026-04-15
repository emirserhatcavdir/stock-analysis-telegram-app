"""Generate price + indicator charts and return as bytes for Telegram."""

from __future__ import annotations

import io
import logging

import matplotlib
matplotlib.use("Agg")  # headless backend – must be before pyplot import
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator

from stock_bot.analysis import compute_bollinger, compute_macd, compute_moving_averages, compute_rsi, download_history
from stock_bot.config import CHART_DPI, CHART_PERIOD, MA_LONG, MA_MID, MA_SHORT, RSI_OVERBOUGHT, RSI_OVERSOLD

logger = logging.getLogger(__name__)


def generate_chart(symbol: str, period: str = CHART_PERIOD) -> bytes | None:
    """Return PNG bytes of a Telegram-friendly 3-panel chart."""
    df = download_history(symbol, period=period)
    if df.empty or "Close" not in df.columns or len(df) < 20:
        return None

    close = df["Close"].astype(float)

    ma20, ma50, ma200 = compute_moving_averages(close)
    rsi = compute_rsi(close)
    bb_upper, bb_mid, bb_lower = compute_bollinger(close)
    macd_line, macd_signal, macd_hist = compute_macd(close)
    dates = df.index

    fig, (ax_price, ax_rsi, ax_macd) = plt.subplots(
        3,
        1,
        figsize=(10.8, 9.2),
        gridspec_kw={"height_ratios": [3.9, 1.3, 1.7]},
        sharex=True,
    )
    fig.suptitle(f"{symbol} ({period})", fontsize=13, fontweight="bold")

    # ── Price panel ───────────────────────────────────────────
    ax_price.plot(dates, close, color="#1f5faa", linewidth=1.8, label="Price")
    ax_price.plot(dates, ma20, color="#ff8b3d", linewidth=1.0, linestyle="--", label=f"MA{MA_SHORT}")
    ax_price.plot(dates, ma50, color="#2a9958", linewidth=1.0, linestyle="--", label=f"MA{MA_MID}")
    if ma200.notna().any():
        ax_price.plot(dates, ma200, color="#cf3a3a", linewidth=1.0, linestyle="--", label=f"MA{MA_LONG}")
    ax_price.plot(dates, bb_upper, color="#6a518a", linewidth=0.9, linestyle=":", label="BB Upper")
    ax_price.plot(dates, bb_mid, color="#7f7f7f", linewidth=0.85, linestyle=":", label="BB Middle")
    ax_price.plot(dates, bb_lower, color="#6a518a", linewidth=0.9, linestyle=":", label="BB Lower")
    ax_price.fill_between(dates, bb_lower, bb_upper, color="#6a518a", alpha=0.08)
    ax_price.set_ylabel("Price (TL)")
    ax_price.legend(loc="upper left", fontsize=8)
    ax_price.grid(True, alpha=0.22)
    ax_price.yaxis.set_major_locator(MaxNLocator(nbins=7))

    # ── RSI panel ─────────────────────────────────────────────
    ax_rsi.plot(dates, rsi, color="#7a54a8", linewidth=1.15)
    ax_rsi.axhline(RSI_OVERBOUGHT, color="red", linewidth=0.7, linestyle="--")
    ax_rsi.axhline(RSI_OVERSOLD, color="green", linewidth=0.7, linestyle="--")
    ax_rsi.fill_between(dates, RSI_OVERBOUGHT, 100, alpha=0.06, color="red")
    ax_rsi.fill_between(dates, 0, RSI_OVERSOLD, alpha=0.06, color="green")
    ax_rsi.set_ylabel("RSI")
    ax_rsi.set_ylim(0, 100)
    ax_rsi.grid(True, alpha=0.22)
    ax_rsi.yaxis.set_major_locator(MaxNLocator(nbins=5))

    # ── MACD panel ────────────────────────────────────────────
    ax_macd.plot(dates, macd_line, color="#1f77b4", linewidth=1.1, label="MACD")
    ax_macd.plot(dates, macd_signal, color="#ff8b3d", linewidth=1.1, label="Signal")
    hist_vals = macd_hist.fillna(0)
    bar_colors = ["#2a9958" if v >= 0 else "#cf3a3a" for v in hist_vals]
    ax_macd.bar(dates, hist_vals, color=bar_colors, alpha=0.34, width=1.0, label="Histogram")
    ax_macd.axhline(0, color="black", linewidth=0.6, alpha=0.5)
    ax_macd.set_ylabel("MACD")
    ax_macd.grid(True, alpha=0.22)
    ax_macd.legend(loc="upper left", fontsize=8)
    ax_macd.yaxis.set_major_locator(MaxNLocator(nbins=6))

    ax_macd.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    fig.autofmt_xdate()
    fig.tight_layout(rect=[0, 0, 1, 0.965])

    buf = io.BytesIO()
    fig.savefig(
        buf,
        format="png",
        dpi=max(CHART_DPI, 120),
        facecolor="white",
        bbox_inches="tight",
    )
    plt.close(fig)
    buf.seek(0)
    return buf.read()
