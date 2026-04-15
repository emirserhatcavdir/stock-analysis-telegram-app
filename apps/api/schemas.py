"""Pydantic response models for Phase 1 API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SymbolInput(BaseModel):
    symbol: str


class PortfolioAddRequest(BaseModel):
    symbol: str
    shares: float = Field(default=0)
    buy_price: float | None = None


class TradeRequest(BaseModel):
    symbol: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    user_id: int | None = None


class PortfolioRemoveRequest(BaseModel):
    symbol: str


class WatchlistAddRequest(BaseModel):
    symbol: str = Field(min_length=1)
    user_id: int | None = None


class WatchlistRemoveRequest(BaseModel):
    symbol: str = Field(min_length=1)
    user_id: int | None = None


class AlertAddRequest(BaseModel):
    symbol: str
    alert_type: str = Field(description="price | score | signal | rsi | macd | ma | change | volume_spike")
    side: str | None = None
    target: float | None = None
    state: str | None = None
    direction: str | None = None
    threshold: float | None = None
    signal: str | None = None
    multiplier: float | None = None


class AlertRemoveRequest(BaseModel):
    symbol: str
    alert_type: str | None = None
    side: str | None = None


class AlertRulePayload(BaseModel):
    symbol: str
    alert_type: str
    side: str | None = None
    target: float | None = None
    state: str | None = None
    direction: str | None = None
    threshold: float | None = None
    signal: str | None = None
    multiplier: float | None = None


class AlertResponse(BaseModel):
    user_id: int
    alerts: dict[str, dict[str, float]] | None = None
    advanced_alerts: dict[str, list[dict]] | None = None
    alert_items: list[dict] = Field(default_factory=list)


class MutationResponse(BaseModel):
    ok: bool = True
    message: str
    user_id: int | None = None


class PortfolioPosition(BaseModel):
    shares: float = Field(default=0)
    buy_price: float = Field(default=0)
    buy_date: str | None = None
    realized_pnl: float | None = None


class PortfolioResponse(BaseModel):
    positions: dict[str, PortfolioPosition]
    total_positions: int


class PortfolioSummarySnapshot(BaseModel):
    total_positions: int = 0
    total_cost: float = 0
    total_value: float = 0
    unrealized_pnl: float = 0
    realized_pnl: float = 0
    net_pnl: float = 0
    best_symbol: str | None = None
    best_pct: float | None = None
    worst_symbol: str | None = None
    worst_pct: float | None = None


class PortfolioPerformanceSnapshot(BaseModel):
    daily_abs: float | None = None
    daily_pct: float | None = None
    weekly_abs: float | None = None
    weekly_pct: float | None = None


class PortfolioAllocationItem(BaseModel):
    symbol: str
    pct: float
    value: float


class PortfolioWinnerLoserItem(BaseModel):
    symbol: str
    unrealized_pct: float
    unrealized_pnl: float
    value: float


class PortfolioInsightsResponse(BaseModel):
    user_id: int
    summary: PortfolioSummarySnapshot
    performance: PortfolioPerformanceSnapshot
    allocation: list[PortfolioAllocationItem] = Field(default_factory=list)
    winners: list[PortfolioWinnerLoserItem] = Field(default_factory=list)
    losers: list[PortfolioWinnerLoserItem] = Field(default_factory=list)


class TradeHistoryItem(BaseModel):
    timestamp: str
    side: str
    symbol: str
    quantity: float
    price: float
    realized_pnl: float = 0


class TradeHistoryResponse(BaseModel):
    user_id: int
    total_realized: float = 0
    trades: list[TradeHistoryItem] = Field(default_factory=list)


class WatchlistResponse(BaseModel):
    chat_id: int | None = None
    symbols: list[str] = Field(default_factory=list)
    watchlists: dict[str, list[str]] | None = None


class ScoreResponse(BaseModel):
    symbol: str
    score: int
    strength: str
    rsi: float | None = None
    ma20: float | None = None
    ma50: float | None = None
    ma200: float | None = None
    ma_note: str | None = None
    trend: str
    ma_alignment: str
    summary: str


class AnalysisResponse(BaseModel):
    symbol: str
    rsi: float | None = None
    ma20: float | None = None
    ma50: float | None = None
    ma200: float | None = None
    ma_note: str | None = None
    trend: str
    commentary: str | None = None
    signal_summary: str


class ScanItem(BaseModel):
    symbol: str
    rsi: float | None = None
    change_pct: float | None = None
    price: float | None = None
    trend: str


class ScanBist30Response(BaseModel):
    universe: str
    analyzed_count: int
    failed_count: int
    oversold: list[ScanItem] = Field(default_factory=list)
    overbought: list[ScanItem] = Field(default_factory=list)
    strong_trend: list[ScanItem] = Field(default_factory=list)


class UserPortfolioResponse(BaseModel):
    user_id: int
    positions: dict[str, PortfolioPosition]
    total_positions: int


class UserWatchlistResponse(BaseModel):
    user_id: int
    symbols: list[str] = Field(default_factory=list)
    count: int = 0


class ScanRankItem(BaseModel):
    rank: int
    symbol: str
    score: int
    signal: str
    strength: str
    rsi: float | None = None
    trend: str | None = None
    summary: str | None = None
    ma20: float | None = None
    ma50: float | None = None
    ma200: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    price: float | None = None
    bb_upper: float | None = None
    bb_lower: float | None = None
    tags: list[str] = Field(default_factory=list)


class ScanResponse(BaseModel):
    universe: str
    count: int
    results: list[ScanRankItem] = Field(default_factory=list)


class SymbolResponse(BaseModel):
    symbol: str
    price: float | None = None
    change_pct: float | None = None
    rsi: float | None = None
    ma20: float | None = None
    ma50: float | None = None
    ma200: float | None = None
    macd: float | None = None
    signal: float | None = None
    histogram: float | None = None
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    trend: str
    score: int
    score_strength: str
    summary: str


class ChartResponse(BaseModel):
    symbol: str
    period: str
    content_type: str = "image/png"


class ChartSeriesPoint(BaseModel):
    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    ma20: float | None = None
    ma50: float | None = None
    ma200: float | None = None
    rsi: float | None = None


class ChartSeriesResponse(BaseModel):
    symbol: str
    period: str
    points: list[ChartSeriesPoint] = Field(default_factory=list)
