"""Market scan logic for stock universes and symbol groups."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from stock_bot.analysis import AnalysisResult, analyze, compute_moving_averages, download_history, normalize_symbol

logger = logging.getLogger(__name__)

# Kept explicit for maintainability; new universes can be added here.
SCAN_UNIVERSES: dict[str, list[str]] = {
    "bist30": [
        "AKBNK", "ALARK", "ASELS", "ASTOR", "BIMAS", "DOHOL", "EKGYO", "ENKAI", "EREGL", "FROTO",
        "GARAN", "GUBRF", "HEKTS", "ISCTR", "KCHOL", "KOZAL", "KRDMD", "ODAS", "OYAKC", "PETKM",
        "PGSUS", "SAHOL", "SASA", "SISE", "TAVHL", "TCELL", "THYAO", "TOASO", "TUPRS", "YKBNK",
    ]
}


@dataclass
class ScanReport:
    universe: str
    analyzed_count: int
    failed_count: int
    oversold: list[AnalysisResult]
    overbought: list[AnalysisResult]
    golden_cross: list[AnalysisResult]
    death_cross: list[AnalysisResult]
    strongest_trend: list[AnalysisResult]
    volume_spikes: list[AnalysisResult]

    def format_text(self) -> str:
        lines = [
            f"*Tarama Sonucu: {self.universe.upper()}*",
            f"Analiz edilen: {self.analyzed_count} | Hata: {self.failed_count}",
            "",
            "*💎 Aşırı Satım (RSI <= 30)*",
        ]

        if self.oversold:
            for r in self.oversold:
                lines.append(f"• {r.symbol}: RSI {r.rsi:.2f} | Fiyat {r.price:.2f} TL")
        else:
            lines.append("• Uygun hisse yok")

        lines.append("")
        lines.append("*🔥 Aşırı Alım (RSI >= 70)*")
        if self.overbought:
            for r in self.overbought:
                lines.append(f"• {r.symbol}: RSI {r.rsi:.2f} | Fiyat {r.price:.2f} TL")
        else:
            lines.append("• Uygun hisse yok")

        lines.append("")
        lines.append("*📈 En Güçlü MA Trendleri*")
        if self.strongest_trend:
            for r in self.strongest_trend:
                score = _ma_trend_score(r)
                lines.append(
                    f"• {r.symbol}: Skor {score} | MA20 {r.ma20:.2f}, MA50 {r.ma50:.2f}, MA200 {r.ma200:.2f}, Fiyat {r.price:.2f}"
                )
        else:
            lines.append("• Uygun hisse yok")

        lines.append("")
        lines.append("*🌅 Golden Cross (MA20, MA50 üzerine çıktı)*")
        if self.golden_cross:
            for r in self.golden_cross:
                lines.append(f"• {r.symbol}: MA20 {r.ma20:.2f} | MA50 {r.ma50:.2f}")
        else:
            lines.append("• Uygun hisse yok")

        lines.append("")
        lines.append("*🌑 Death Cross (MA20, MA50 altına indi)*")
        if self.death_cross:
            for r in self.death_cross:
                lines.append(f"• {r.symbol}: MA20 {r.ma20:.2f} | MA50 {r.ma50:.2f}")
        else:
            lines.append("• Uygun hisse yok")

        lines.append("")
        lines.append("*📦 Hacim Spike*")
        if self.volume_spikes:
            for r in self.volume_spikes:
                ratio = r.volume_ratio if r.volume_ratio is not None else 0
                lines.append(f"• {r.symbol}: Hacim Oranı {ratio:.2f} | Değişim {r.change_pct:+.2f}%")
        else:
            lines.append("• Uygun hisse yok")

        return "\n".join(lines)


def _normalize_unique(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for s in symbols:
        n = normalize_symbol(s)
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def resolve_symbols(
    target: str,
    portfolio_symbols: list[str] | None = None,
    watchlist_symbols: list[str] | None = None,
) -> list[str] | None:
    key = target.strip().lower()
    if key == "portfolio":
        return _normalize_unique(portfolio_symbols or [])
    if key == "watchlist":
        return _normalize_unique(watchlist_symbols or [])

    universe = SCAN_UNIVERSES.get(key)
    if universe is None:
        return None
    return _normalize_unique(universe)


def _ma_trend_score(result: AnalysisResult) -> int:
    if (
        result.price is None
        or result.ma20 is None
        or result.ma50 is None
        or result.ma200 is None
    ):
        return -99

    score = 0
    if result.price > result.ma20:
        score += 1
    if result.ma20 > result.ma50:
        score += 1
    if result.ma50 > result.ma200:
        score += 1
    if result.price > result.ma200:
        score += 1
    return score


def _cross_signal(symbol: str) -> str | None:
    """Return 'golden', 'death' or None based on recent MA20/MA50 crossover."""
    df = download_history(symbol, period="6mo")
    if df.empty or "Close" not in df.columns:
        return None

    close = df["Close"].astype(float)
    if len(close) < 60:
        return None

    ma20, ma50, _ = compute_moving_averages(close)
    if len(ma20) < 2 or len(ma50) < 2:
        return None

    prev20 = ma20.iloc[-2]
    prev50 = ma50.iloc[-2]
    cur20 = ma20.iloc[-1]
    cur50 = ma50.iloc[-1]

    if any(v != v for v in (prev20, prev50, cur20, cur50)):  # NaN check
        return None

    prev_diff = prev20 - prev50
    cur_diff = cur20 - cur50
    if prev_diff <= 0 and cur_diff > 0:
        return "golden"
    if prev_diff >= 0 and cur_diff < 0:
        return "death"
    return None


def run_scan(
    universe: str,
    portfolio_symbols: list[str] | None = None,
    watchlist_symbols: list[str] | None = None,
) -> ScanReport | None:
    symbols = resolve_symbols(universe, portfolio_symbols=portfolio_symbols, watchlist_symbols=watchlist_symbols)
    if symbols is None:
        return None

    analyzed: list[AnalysisResult] = []
    failed = 0
    golden_cross: list[AnalysisResult] = []
    death_cross: list[AnalysisResult] = []

    for symbol in symbols:
        try:
            res = analyze(symbol)
        except Exception:
            logger.exception("run_scan: analyze failed for symbol=%s", symbol)
            failed += 1
            continue

        if res is None or res.rsi is None or res.price is None:
            failed += 1
            continue

        analyzed.append(res)

        try:
            cross = _cross_signal(symbol)
        except Exception:
            logger.exception("run_scan: cross-signal failed for symbol=%s", symbol)
            cross = None

        if cross == "golden":
            golden_cross.append(res)
        elif cross == "death":
            death_cross.append(res)

    oversold = sorted(
        [x for x in analyzed if x.rsi is not None and x.rsi <= 30],
        key=lambda x: x.rsi if x.rsi is not None else 999,
    )[:7]

    overbought = sorted(
        [x for x in analyzed if x.rsi is not None and x.rsi >= 70],
        key=lambda x: x.rsi if x.rsi is not None else -999,
        reverse=True,
    )[:7]

    strongest_trend = sorted(
        [x for x in analyzed if _ma_trend_score(x) >= 0],
        key=lambda x: (_ma_trend_score(x), x.change_pct or 0),
        reverse=True,
    )[:7]

    volume_spikes = sorted(
        [x for x in analyzed if x.is_volume_spike],
        key=lambda x: x.volume_ratio or 0,
        reverse=True,
    )[:7]

    golden_cross_sorted = sorted(
        golden_cross,
        key=lambda x: x.change_pct or 0,
        reverse=True,
    )[:7]

    death_cross_sorted = sorted(
        death_cross,
        key=lambda x: x.change_pct or 0,
    )[:7]

    return ScanReport(
        universe=universe,
        analyzed_count=len(analyzed),
        failed_count=failed,
        oversold=oversold,
        overbought=overbought,
        golden_cross=golden_cross_sorted,
        death_cross=death_cross_sorted,
        strongest_trend=strongest_trend,
        volume_spikes=volume_spikes,
    )
