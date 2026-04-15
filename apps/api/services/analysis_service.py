"""Analysis and chart service shared by Telegram bot and FastAPI routes."""

from __future__ import annotations

from typing import Any

from stock_bot.analysis import analyze, compute_moving_averages, compute_rsi, download_history, normalize_symbol
from stock_bot.charts import generate_chart
from stock_bot.scoring import score_analysis


def get_analysis(symbol: str, period: str = "1y") -> dict[str, Any] | None:
    normalized = normalize_symbol(symbol)
    result = analyze(normalized, period=period)
    if result is None:
        return None
    return {
        "symbol": normalized,
        "rsi": result.rsi,
        "ma20": result.ma20,
        "ma50": result.ma50,
        "ma200": result.ma200,
        "ma_note": result.ma_availability_note,
        "trend": result.trend,
        "commentary": result.commentary,
        "signal_summary": result.signal_summary,
    }


def get_symbol_details(symbol: str) -> dict[str, Any] | None:
    normalized = normalize_symbol(symbol)
    result = analyze(normalized)
    if result is None:
        return None
    scored = score_analysis(result)
    return {
        "symbol": normalized,
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


def get_symbol_chart(symbol: str, period: str = "6mo") -> bytes | None:
    normalized = normalize_symbol(symbol)
    return generate_chart(normalized, period=period)


def get_symbol_chart_series(symbol: str, period: str = "6mo", limit: int = 240) -> dict[str, Any] | None:
    normalized = normalize_symbol(symbol)
    df = download_history(normalized, period=period)
    if df.empty or "Close" not in df.columns:
        return None

    close = df["Close"].astype(float)
    open_ = df["Open"].astype(float) if "Open" in df.columns else close
    high = df["High"].astype(float) if "High" in df.columns else close
    low = df["Low"].astype(float) if "Low" in df.columns else close
    volume = df["Volume"].astype(float) if "Volume" in df.columns else None
    ma20, ma50, ma200 = compute_moving_averages(close)
    rsi = compute_rsi(close)

    frame = df[["Close"]].copy()
    frame["open"] = open_
    frame["high"] = high
    frame["low"] = low
    if volume is not None:
        frame["volume"] = volume
    frame["ma20"] = ma20
    frame["ma50"] = ma50
    frame["ma200"] = ma200
    frame["rsi"] = rsi
    frame = frame.tail(max(int(limit), 30))

    points: list[dict[str, Any]] = []
    for ts, row in frame.iterrows():
        points.append(
            {
                "date": ts.strftime("%Y-%m-%d"),
                "open": float(row["open"]) if row["open"] == row["open"] else None,
                "high": float(row["high"]) if row["high"] == row["high"] else None,
                "low": float(row["low"]) if row["low"] == row["low"] else None,
                "close": float(row["Close"]) if row["Close"] == row["Close"] else None,
                "volume": float(row.get("volume")) if row.get("volume") == row.get("volume") else None,
                "ma20": float(row["ma20"]) if row["ma20"] == row["ma20"] else None,
                "ma50": float(row["ma50"]) if row["ma50"] == row["ma50"] else None,
                "ma200": float(row["ma200"]) if row["ma200"] == row["ma200"] else None,
                "rsi": float(row["rsi"]) if row["rsi"] == row["rsi"] else None,
            }
        )

    return {
        "symbol": normalized,
        "period": period,
        "points": points,
    }
