"""Portfolio endpoints for the Mini App."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from apps.api.deps import load_portfolio
from apps.api.schemas import (
    MutationResponse,
    PortfolioAllocationItem,
    PortfolioInsightsResponse,
    PortfolioPerformanceSnapshot,
    PortfolioPosition,
    PortfolioResponse,
    PortfolioSummarySnapshot,
    PortfolioWinnerLoserItem,
    TradeHistoryItem,
    TradeHistoryResponse,
    TradeRequest,
)
from stock_bot.analysis import normalize_symbol
from stock_bot.data_manager import apply_trade, load_trades
from stock_bot.portfolio_analytics import (
    compute_portfolio_analytics,
    get_allocation,
    get_best_position,
    get_losers,
    get_winners,
    get_worst_position,
)

router = APIRouter(prefix="/api", tags=["portfolio"])


@router.get("/portfolio", response_model=PortfolioResponse)
def get_portfolio(user_id: int | None = Query(default=None)) -> PortfolioResponse:
    raw = load_portfolio(user_id or 0)
    positions: dict[str, PortfolioPosition] = {}
    for symbol, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        positions[symbol] = PortfolioPosition(
            shares=float(entry.get("shares", 0) or 0),
            buy_price=float(entry.get("buy_price", 0) or 0),
            buy_date=entry.get("buy_date"),
            realized_pnl=entry.get("realized_pnl"),
        )
    return PortfolioResponse(positions=positions, total_positions=len(positions))


@router.get("/portfolio/insights", response_model=PortfolioInsightsResponse)
def portfolio_insights(user_id: int | None = Query(default=None)) -> PortfolioInsightsResponse:
    resolved_user_id = user_id or 0
    raw_portfolio = load_portfolio(resolved_user_id)
    raw_trades = load_trades(resolved_user_id)
    analytics = compute_portfolio_analytics(raw_portfolio, raw_trades)

    best = get_best_position(analytics)
    worst = get_worst_position(analytics)
    allocation_rows = get_allocation(analytics)
    winners = get_winners(analytics, limit=5)
    losers = get_losers(analytics, limit=5)

    return PortfolioInsightsResponse(
        user_id=resolved_user_id,
        summary=PortfolioSummarySnapshot(
            total_positions=len(analytics.positions),
            total_cost=analytics.total_cost,
            total_value=analytics.total_value,
            unrealized_pnl=analytics.unrealized_pnl,
            realized_pnl=analytics.realized_pnl,
            net_pnl=analytics.net_pnl,
            best_symbol=best.symbol if best else None,
            best_pct=best.unrealized_pct if best else None,
            worst_symbol=worst.symbol if worst else None,
            worst_pct=worst.unrealized_pct if worst else None,
        ),
        performance=PortfolioPerformanceSnapshot(
            daily_abs=analytics.daily_abs,
            daily_pct=analytics.daily_pct,
            weekly_abs=analytics.weekly_abs,
            weekly_pct=analytics.weekly_pct,
        ),
        allocation=[
            PortfolioAllocationItem(symbol=pos.symbol, pct=pct, value=pos.value)
            for pos, pct in allocation_rows
        ],
        winners=[
            PortfolioWinnerLoserItem(
                symbol=pos.symbol,
                unrealized_pct=pos.unrealized_pct,
                unrealized_pnl=pos.unrealized_pnl,
                value=pos.value,
            )
            for pos in winners
        ],
        losers=[
            PortfolioWinnerLoserItem(
                symbol=pos.symbol,
                unrealized_pct=pos.unrealized_pct,
                unrealized_pnl=pos.unrealized_pnl,
                value=pos.value,
            )
            for pos in losers
        ],
    )


@router.get("/portfolio/trades", response_model=TradeHistoryResponse)
def portfolio_trades(user_id: int | None = Query(default=None), limit: int = Query(default=20, ge=1, le=200)) -> TradeHistoryResponse:
    resolved_user_id = user_id or 0
    rows = load_trades(resolved_user_id)
    recent = rows[-limit:]
    total_realized = sum(float(item.get("realized_pnl", 0) or 0) for item in rows)

    return TradeHistoryResponse(
        user_id=resolved_user_id,
        total_realized=total_realized,
        trades=[
            TradeHistoryItem(
                timestamp=str(item.get("timestamp", "")),
                side=str(item.get("side", "")),
                symbol=str(item.get("symbol", "")),
                quantity=float(item.get("quantity", 0) or 0),
                price=float(item.get("price", 0) or 0),
                realized_pnl=float(item.get("realized_pnl", 0) or 0),
            )
            for item in reversed(recent)
        ],
    )


def _trade(user_id: int | None, side: str, payload: TradeRequest) -> MutationResponse:
    normalized = normalize_symbol(payload.symbol)
    if not normalized:
        raise HTTPException(status_code=400, detail="symbol is required")

    resolved_user_id = user_id if user_id is not None else payload.user_id
    ok, message, _trade_row = apply_trade(
        user_id=resolved_user_id or 0,
        side=side,
        symbol=normalized,
        quantity=payload.quantity,
        price=payload.price,
        timestamp=datetime.now().isoformat(timespec="seconds"),
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return MutationResponse(ok=True, message=f"{normalized} {side} recorded", user_id=resolved_user_id or 0)


@router.post("/portfolio/buy", response_model=MutationResponse)
def buy(payload: TradeRequest) -> MutationResponse:
    return _trade(payload.user_id, "buy", payload)


@router.post("/portfolio/sell", response_model=MutationResponse)
def sell(payload: TradeRequest) -> MutationResponse:
    return _trade(payload.user_id, "sell", payload)

