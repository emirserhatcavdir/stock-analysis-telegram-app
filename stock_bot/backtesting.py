"""Simple backtesting engine for indicator-based stock strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from stock_bot.analysis import compute_rsi, download_history, normalize_symbol


@dataclass
class BacktestTrade:
    buy_date: str
    sell_date: str
    buy_price: float
    sell_price: float
    return_pct: float


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def run_backtest(ticker: str, strategy: dict[str, Any]) -> dict[str, Any]:
    """Run a simple RSI strategy backtest on yfinance historical data.

    Expected strategy keys (all optional):
    - period: yfinance period string, default "1y"
    - rsi_period: RSI lookback, default 14
    - buy_below: buy threshold, default 30
    - sell_above: sell threshold, default 70
    - initial_capital: starting capital, default 100000
    """
    symbol = normalize_symbol(ticker)
    period = str(strategy.get("period", "1y"))
    rsi_period = int(_to_float(strategy.get("rsi_period", 14), 14))
    buy_below = _to_float(strategy.get("buy_below", 30), 30)
    sell_above = _to_float(strategy.get("sell_above", 70), 70)
    initial_capital = _to_float(strategy.get("initial_capital", 100000), 100000)

    df = download_history(symbol, period=period)
    if df.empty or "Close" not in df.columns or len(df) < max(30, rsi_period + 5):
        return {
            "ticker": symbol,
            "strategy": {
                "buy_rule": f"RSI < {buy_below}",
                "sell_rule": f"RSI > {sell_above}",
            },
            "total_return_pct": 0.0,
            "win_rate_pct": 0.0,
            "number_of_trades": 0,
            "initial_capital": initial_capital,
            "final_capital": initial_capital,
            "trades": [],
            "error": "Not enough historical data",
        }

    close = df["Close"].astype(float)
    rsi = compute_rsi(close, period=rsi_period)

    cash = initial_capital
    shares = 0.0
    in_position = False
    entry_price = 0.0
    entry_date = ""

    trades: list[BacktestTrade] = []

    for idx in range(1, len(close)):
        price = float(close.iloc[idx])
        rsi_val = float(rsi.iloc[idx])
        date_str = str(close.index[idx].date())

        if not in_position and rsi_val < buy_below and price > 0:
            shares = cash / price
            cash = 0.0
            in_position = True
            entry_price = price
            entry_date = date_str
            continue

        if in_position and rsi_val > sell_above:
            cash = shares * price
            trade_ret = ((price / entry_price) - 1.0) * 100 if entry_price > 0 else 0.0
            trades.append(
                BacktestTrade(
                    buy_date=entry_date,
                    sell_date=date_str,
                    buy_price=entry_price,
                    sell_price=price,
                    return_pct=trade_ret,
                )
            )
            shares = 0.0
            in_position = False

    # Mark-to-market for open position at last close
    final_price = float(close.iloc[-1])
    final_capital = cash if not in_position else shares * final_price

    number_of_trades = len(trades)
    wins = len([t for t in trades if t.return_pct > 0])
    win_rate = (wins / number_of_trades) * 100 if number_of_trades > 0 else 0.0
    total_return = ((final_capital / initial_capital) - 1.0) * 100 if initial_capital > 0 else 0.0

    return {
        "ticker": symbol,
        "strategy": {
            "buy_rule": f"RSI < {buy_below}",
            "sell_rule": f"RSI > {sell_above}",
            "period": period,
            "rsi_period": rsi_period,
        },
        "total_return_pct": round(total_return, 2),
        "win_rate_pct": round(win_rate, 2),
        "number_of_trades": number_of_trades,
        "initial_capital": round(initial_capital, 2),
        "final_capital": round(final_capital, 2),
        "trades": [
            {
                "buy_date": t.buy_date,
                "sell_date": t.sell_date,
                "buy_price": round(t.buy_price, 4),
                "sell_price": round(t.sell_price, 4),
                "return_pct": round(t.return_pct, 2),
            }
            for t in trades
        ],
    }
