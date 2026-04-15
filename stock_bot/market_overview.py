"""Market overview helpers for BIST snapshots and movers."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from stock_bot.analysis import download_history, normalize_symbol
from stock_bot.scanner import SCAN_UNIVERSES


@dataclass
class MarketRow:
    symbol: str
    price: float
    change_pct: float
    volume: float | None
    volume_ratio: float | None
    trend: str


@dataclass
class MarketOverview:
    universe: str
    analyzed_count: int
    failed_count: int
    gainers: list[MarketRow]
    losers: list[MarketRow]
    volume_leaders: list[MarketRow]
    uptrend_count: int
    downtrend_count: int
    sideways_count: int
    avg_change_pct: float | None

    def format_market_text(self) -> str:
        lines = [
            f"*Piyasa Ozeti: {self.universe.upper()}*",
            f"Analiz edilen: {self.analyzed_count} | Hata: {self.failed_count}",
        ]

        if self.avg_change_pct is not None:
            lines.append(f"Ortalama gunluk degisim: {self.avg_change_pct:+.2f}%")
        lines.append(
            f"Trend dagilimi: Yukselis {self.uptrend_count} | Dusus {self.downtrend_count} | Yatay {self.sideways_count}"
        )

        lines.append("")
        lines.append("*En Cok Yukselenler*")
        if self.gainers:
            for row in self.gainers:
                lines.append(f"• {row.symbol}: {row.change_pct:+.2f}% | {row.price:.2f} TL")
        else:
            lines.append("• Veri yok")

        lines.append("")
        lines.append("*En Cok Dusenler*")
        if self.losers:
            for row in self.losers:
                lines.append(f"• {row.symbol}: {row.change_pct:+.2f}% | {row.price:.2f} TL")
        else:
            lines.append("• Veri yok")

        lines.append("")
        lines.append("*Hacim Liderleri*")
        if self.volume_leaders:
            for row in self.volume_leaders:
                ratio_text = f"{row.volume_ratio:.2f}x" if row.volume_ratio is not None else "n/a"
                volume_text = f"{row.volume:,.0f}" if row.volume is not None else "n/a"
                lines.append(
                    f"• {row.symbol}: Hacim {volume_text} | Oran {ratio_text} | Degisim {row.change_pct:+.2f}%"
                )
        else:
            lines.append("• Veri yok")

        return "\n".join(lines)

    def format_movers_text(self) -> str:
        lines = [
            f"*Mover Listesi: {self.universe.upper()}*",
            f"Analiz edilen: {self.analyzed_count} | Hata: {self.failed_count}",
            "",
            "*Top Gainers*",
        ]
        if self.gainers:
            for i, row in enumerate(self.gainers, start=1):
                lines.append(f"{i}. {row.symbol} — {row.change_pct:+.2f}% | {row.price:.2f} TL")
        else:
            lines.append("Veri yok")

        lines.append("")
        lines.append("*Top Losers*")
        if self.losers:
            for i, row in enumerate(self.losers, start=1):
                lines.append(f"{i}. {row.symbol} — {row.change_pct:+.2f}% | {row.price:.2f} TL")
        else:
            lines.append("Veri yok")

        return "\n".join(lines)

    def format_volume_leaders_text(self) -> str:
        lines = [
            f"*Hacim Liderleri: {self.universe.upper()}*",
            f"Analiz edilen: {self.analyzed_count} | Hata: {self.failed_count}",
            "",
        ]
        if self.volume_leaders:
            for i, row in enumerate(self.volume_leaders, start=1):
                ratio_text = f"{row.volume_ratio:.2f}x" if row.volume_ratio is not None else "n/a"
                volume_text = f"{row.volume:,.0f}" if row.volume is not None else "n/a"
                lines.append(
                    f"{i}. {row.symbol} — Hacim {volume_text} | Oran {ratio_text} | {row.change_pct:+.2f}%"
                )
        else:
            lines.append("Veri yok")
        return "\n".join(lines)


def _safe_float(value: object) -> float | None:
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _classify_trend(price: float | None, ma20: float | None, ma50: float | None) -> str:
    if price is None or ma20 is None or ma50 is None:
        return "sideways"
    if price > ma20 > ma50:
        return "up"
    if price < ma20 < ma50:
        return "down"
    return "sideways"


def _build_row(symbol: str) -> MarketRow | None:
    df = download_history(symbol, period="6mo")
    if df.empty or "Close" not in df.columns:
        return None

    close = df["Close"].astype(float)
    if len(close) < 2:
        return None

    price = _safe_float(close.iloc[-1])
    prev = _safe_float(close.iloc[-2])
    if price is None or prev is None or prev == 0:
        return None

    change_pct = ((price - prev) / prev) * 100
    ma20 = _safe_float(close.rolling(window=20, min_periods=20).mean().iloc[-1])
    ma50 = _safe_float(close.rolling(window=50, min_periods=50).mean().iloc[-1])

    volume = None
    volume_ratio = None
    if "Volume" in df.columns:
        vol = df["Volume"].astype(float)
        volume = _safe_float(vol.iloc[-1])
        vol_ma20 = _safe_float(vol.rolling(window=20, min_periods=20).mean().iloc[-1])
        if volume is not None and vol_ma20 not in (None, 0):
            volume_ratio = volume / vol_ma20

    return MarketRow(
        symbol=symbol,
        price=price,
        change_pct=change_pct,
        volume=volume,
        volume_ratio=volume_ratio,
        trend=_classify_trend(price, ma20, ma50),
    )


def get_universe_symbols(universe: str = "bist30") -> list[str] | None:
    symbols = SCAN_UNIVERSES.get(universe.lower())
    if symbols is None:
        return None
    return [normalize_symbol(s) for s in symbols]


def build_market_overview(universe: str = "bist30", top_n: int = 5) -> MarketOverview | None:
    symbols = get_universe_symbols(universe)
    if not symbols:
        return None

    rows: list[MarketRow] = []
    failed = 0
    for symbol in symbols:
        row = _build_row(symbol)
        if row is None:
            failed += 1
            continue
        rows.append(row)

    if not rows:
        return MarketOverview(
            universe=universe,
            analyzed_count=0,
            failed_count=failed,
            gainers=[],
            losers=[],
            volume_leaders=[],
            uptrend_count=0,
            downtrend_count=0,
            sideways_count=0,
            avg_change_pct=None,
        )

    sorted_by_change = sorted(rows, key=lambda r: r.change_pct, reverse=True)
    sorted_by_volume = sorted(
        rows,
        key=lambda r: (
            r.volume_ratio if r.volume_ratio is not None else -1,
            r.volume if r.volume is not None else -1,
        ),
        reverse=True,
    )

    avg_change = sum(r.change_pct for r in rows) / len(rows)
    up = sum(1 for r in rows if r.trend == "up")
    down = sum(1 for r in rows if r.trend == "down")
    sideways = len(rows) - up - down

    return MarketOverview(
        universe=universe,
        analyzed_count=len(rows),
        failed_count=failed,
        gainers=sorted_by_change[:top_n],
        losers=list(reversed(sorted_by_change[-top_n:])),
        volume_leaders=sorted_by_volume[:top_n],
        uptrend_count=up,
        downtrend_count=down,
        sideways_count=sideways,
        avg_change_pct=avg_change,
    )