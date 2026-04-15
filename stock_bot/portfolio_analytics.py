"""Portfolio analytics helpers for summary, performance, allocation, winners/losers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from stock_bot.analysis import download_history, get_current_price


@dataclass
class PositionSnapshot:
    symbol: str
    shares: float
    buy_price: float
    current_price: float
    cost: float
    value: float
    unrealized_pnl: float
    unrealized_pct: float


@dataclass
class PortfolioAnalytics:
    positions: list[PositionSnapshot]
    total_cost: float
    total_value: float
    unrealized_pnl: float
    realized_pnl: float
    net_pnl: float
    daily_abs: float | None
    daily_pct: float | None
    weekly_abs: float | None
    weekly_pct: float | None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _previous_closes(symbol: str) -> tuple[float | None, float | None]:
    """Return (previous_day_close, ~previous_week_close)."""
    df = download_history(symbol, period="1mo")
    if df.empty or "Close" not in df.columns:
        return None, None

    close = df["Close"].astype(float)
    prev_day = float(close.iloc[-2]) if len(close) >= 2 else None
    prev_week = float(close.iloc[-6]) if len(close) >= 6 else None
    return prev_day, prev_week


def compute_portfolio_analytics(
    portfolio: dict[str, dict],
    trades: list[dict[str, Any]],
) -> PortfolioAnalytics:
    positions: list[PositionSnapshot] = []

    total_cost = 0.0
    total_value = 0.0

    daily_ref_value = 0.0
    daily_abs = 0.0
    daily_valid = False

    weekly_ref_value = 0.0
    weekly_abs = 0.0
    weekly_valid = False

    for symbol, entry in portfolio.items():
        shares = _safe_float(entry.get("shares", 0), 0.0)
        buy_price = _safe_float(entry.get("buy_price", 0), 0.0)
        if shares <= 0 or buy_price <= 0:
            continue

        current = get_current_price(symbol)
        if current is None:
            continue

        cost = shares * buy_price
        value = shares * current
        unrealized = value - cost
        unrealized_pct = ((current / buy_price) - 1.0) * 100 if buy_price > 0 else 0.0

        positions.append(
            PositionSnapshot(
                symbol=symbol,
                shares=shares,
                buy_price=buy_price,
                current_price=current,
                cost=cost,
                value=value,
                unrealized_pnl=unrealized,
                unrealized_pct=unrealized_pct,
            )
        )

        total_cost += cost
        total_value += value

        prev_day, prev_week = _previous_closes(symbol)
        if prev_day is not None and prev_day > 0:
            ref_day_value = shares * prev_day
            daily_ref_value += ref_day_value
            daily_abs += value - ref_day_value
            daily_valid = True

        if prev_week is not None and prev_week > 0:
            ref_week_value = shares * prev_week
            weekly_ref_value += ref_week_value
            weekly_abs += value - ref_week_value
            weekly_valid = True

    realized_pnl = 0.0
    for t in trades:
        side = str(t.get("side", "")).lower()
        if side != "sell":
            continue
        realized_pnl += _safe_float(t.get("realized_pnl", 0), 0.0)

    unrealized_pnl = total_value - total_cost
    net_pnl = realized_pnl + unrealized_pnl

    daily_pct = None
    if daily_valid and daily_ref_value > 0:
        daily_pct = (daily_abs / daily_ref_value) * 100.0
    else:
        daily_abs = None

    weekly_pct = None
    if weekly_valid and weekly_ref_value > 0:
        weekly_pct = (weekly_abs / weekly_ref_value) * 100.0
    else:
        weekly_abs = None

    return PortfolioAnalytics(
        positions=positions,
        total_cost=total_cost,
        total_value=total_value,
        unrealized_pnl=unrealized_pnl,
        realized_pnl=realized_pnl,
        net_pnl=net_pnl,
        daily_abs=daily_abs,
        daily_pct=daily_pct,
        weekly_abs=weekly_abs,
        weekly_pct=weekly_pct,
    )


def get_allocation(analytics: PortfolioAnalytics) -> list[tuple[PositionSnapshot, float]]:
    if analytics.total_value <= 0:
        return []
    rows = [
        (p, (p.value / analytics.total_value) * 100.0)
        for p in analytics.positions
    ]
    return sorted(rows, key=lambda x: x[1], reverse=True)


def get_winners(analytics: PortfolioAnalytics, limit: int = 5) -> list[PositionSnapshot]:
    positives = [p for p in analytics.positions if p.unrealized_pct >= 0]
    return sorted(positives, key=lambda p: p.unrealized_pct, reverse=True)[:limit]


def get_losers(analytics: PortfolioAnalytics, limit: int = 5) -> list[PositionSnapshot]:
    negatives = [p for p in analytics.positions if p.unrealized_pct < 0]
    return sorted(negatives, key=lambda p: p.unrealized_pct)[:limit]


def get_best_position(analytics: PortfolioAnalytics) -> PositionSnapshot | None:
    if not analytics.positions:
        return None
    return max(analytics.positions, key=lambda p: p.unrealized_pct)


def get_worst_position(analytics: PortfolioAnalytics) -> PositionSnapshot | None:
    if not analytics.positions:
        return None
    return min(analytics.positions, key=lambda p: p.unrealized_pct)
