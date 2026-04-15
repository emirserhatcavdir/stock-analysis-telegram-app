"""Fundamental analysis helpers using yfinance metadata."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import RLock
from typing import Any

import yfinance as yf

_fund_cache_lock = RLock()
_fund_cache: dict[str, tuple[float, FundamentalSnapshot | None]] = {}
_FUND_CACHE_TTL_OK = 300
_FUND_CACHE_TTL_MISS = 30


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_number(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{decimals}f}"


def _fmt_market_cap(value: float | None) -> str:
    if value is None:
        return "n/a"
    n = abs(value)
    sign = "-" if value < 0 else ""
    if n >= 1_000_000_000_000:
        return f"{sign}{n / 1_000_000_000_000:.2f}T"
    if n >= 1_000_000_000:
        return f"{sign}{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{sign}{n / 1_000_000:.2f}M"
    return f"{value:,.0f}"


@dataclass
class FundamentalSnapshot:
    symbol: str
    short_name: str | None
    sector: str | None
    industry: str | None
    market_cap: float | None
    pe_trailing: float | None
    pe_forward: float | None
    pb: float | None
    eps: float | None
    roe: float | None
    debt_to_equity: float | None
    dividend_yield: float | None
    beta: float | None
    week52_low: float | None
    week52_high: float | None
    current_price: float | None

    def quality_label(self) -> str:
        score = 0
        checks = 0

        if self.pe_trailing is not None:
            checks += 1
            if 0 < self.pe_trailing <= 20:
                score += 1

        if self.pb is not None:
            checks += 1
            if 0 < self.pb <= 3:
                score += 1

        if self.roe is not None:
            checks += 1
            if self.roe >= 0.10:
                score += 1

        if self.debt_to_equity is not None:
            checks += 1
            if self.debt_to_equity <= 150:
                score += 1

        if checks == 0:
            return "Yetersiz veri"
        ratio = score / checks
        if ratio >= 0.75:
            return "Gorece guclu"
        if ratio >= 0.50:
            return "Dengeli"
        return "Temkinli"

    def format_text(self) -> str:
        lines = [
            f"*{self.symbol} Fundamental*",
        ]
        if self.short_name:
            lines.append(f"Sirket: {self.short_name}")
        lines.append(f"Sektor / Endustri: {self.sector or 'n/a'} / {self.industry or 'n/a'}")
        lines.append(f"Piyasa Degeri: {_fmt_market_cap(self.market_cap)}")
        lines.append(
            "Degerleme: "
            f"F/K {_fmt_number(self.pe_trailing)} | "
            f"Ileri F/K {_fmt_number(self.pe_forward)} | "
            f"PD/DD {_fmt_number(self.pb)}"
        )
        lines.append(
            "Karlilik/Finansal: "
            f"EPS {_fmt_number(self.eps)} | "
            f"ROE {_fmt_number(self.roe * 100 if self.roe is not None else None)}% | "
            f"Borcluluk {_fmt_number(self.debt_to_equity)}"
        )
        lines.append(
            "Piyasa Riski: "
            f"Beta {_fmt_number(self.beta)} | "
            f"Temettu {_fmt_number(self.dividend_yield * 100 if self.dividend_yield is not None else None)}%"
        )
        lines.append(
            f"52H Aralik: {_fmt_number(self.week52_low)} - {_fmt_number(self.week52_high)} | Fiyat: {_fmt_number(self.current_price)}"
        )
        lines.append(f"Kalite Etiketi: {self.quality_label()}")
        return "\n".join(lines)

    def format_compact_row(self) -> str:
        return (
            f"• {self.symbol}: F/K {_fmt_number(self.pe_trailing)} | "
            f"PD/DD {_fmt_number(self.pb)} | "
            f"ROE {_fmt_number(self.roe * 100 if self.roe is not None else None)}% | "
            f"Kalite {self.quality_label()}"
        )


def get_fundamentals(symbol: str) -> FundamentalSnapshot | None:
    now = time.time()
    with _fund_cache_lock:
        cached = _fund_cache.get(symbol)
        if cached is not None:
            expires_at, snapshot = cached
            if expires_at > now:
                return snapshot

    try:
        info = yf.Ticker(symbol).info or {}
    except Exception:
        with _fund_cache_lock:
            _fund_cache[symbol] = (now + _FUND_CACHE_TTL_MISS, None)
        return None

    # If both price and market cap are missing, data source is likely unavailable.
    current_price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
    market_cap = _safe_float(info.get("marketCap"))
    if current_price is None and market_cap is None:
        with _fund_cache_lock:
            _fund_cache[symbol] = (now + _FUND_CACHE_TTL_MISS, None)
        return None

    snapshot = FundamentalSnapshot(
        symbol=symbol,
        short_name=str(info.get("shortName") or "").strip() or None,
        sector=str(info.get("sector") or "").strip() or None,
        industry=str(info.get("industry") or "").strip() or None,
        market_cap=market_cap,
        pe_trailing=_safe_float(info.get("trailingPE")),
        pe_forward=_safe_float(info.get("forwardPE")),
        pb=_safe_float(info.get("priceToBook")),
        eps=_safe_float(info.get("trailingEps")),
        roe=_safe_float(info.get("returnOnEquity")),
        debt_to_equity=_safe_float(info.get("debtToEquity")),
        dividend_yield=_safe_float(info.get("dividendYield")),
        beta=_safe_float(info.get("beta")),
        week52_low=_safe_float(info.get("fiftyTwoWeekLow")),
        week52_high=_safe_float(info.get("fiftyTwoWeekHigh")),
        current_price=current_price,
    )
    with _fund_cache_lock:
        _fund_cache[symbol] = (now + _FUND_CACHE_TTL_OK, snapshot)
    return snapshot