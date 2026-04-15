"""Signal scoring engine for symbols and symbol lists."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from stock_bot.analysis import AnalysisResult, analyze, normalize_symbol

logger = logging.getLogger(__name__)


@dataclass
class ScoreResult:
    symbol: str
    score: int
    signal: str
    strength: str
    reasons: list[str]

    def format_text(self) -> str:
        reason_text = ", ".join(self.reasons) if self.reasons else "n/a"
        return (
            f"*{self.symbol}*\n"
            f"Skor: *{self.score}/100*\n"
            f"Sinyal: {self.signal}\n"
            f"Güç: {self.strength}\n"
            f"Açıklama: {reason_text}"
        )


def _signal_label(score: int) -> str:
    if score >= 70:
        return "Strong Buy"
    if score >= 56:
        return "Buy"
    if score >= 44:
        return "Neutral"
    return "Sell"


def _strength(score: int) -> str:
    if score >= 70:
        return "strong"
    if score >= 56:
        return "moderate"
    if score >= 44:
        return "balanced"
    if score >= 34:
        return "weak"
    return "very_weak"


def score_analysis(result: AnalysisResult) -> ScoreResult:
    if result.score is not None:
        score = int(result.score)
        signal = str(result.score_signal or _signal_label(score))
        logger.debug(
            "score_analysis(%s): using analysis score=%s signal=%s",
            result.symbol,
            score,
            signal,
        )
        return ScoreResult(
            symbol=result.symbol,
            score=score,
            signal=signal,
            strength=_strength(score),
            reasons=["analysis pipeline score"],
        )

    score = 0
    reasons: list[str] = []

    # 1) RSI (0-20)
    if result.rsi is None:
        score += 8
        reasons.append("RSI verisi sınırlı")
    elif result.rsi <= 30:
        score += 20
        reasons.append("RSI aşırı satım (pozitif)")
    elif result.rsi < 45:
        score += 14
        reasons.append("RSI düşük-orta")
    elif result.rsi <= 60:
        score += 10
        reasons.append("RSI nötr")
    elif result.rsi < 70:
        score += 6
        reasons.append("RSI yüksek")
    else:
        score += 2
        reasons.append("RSI aşırı alım (risk)")

    # 2) MA alignment (0-25)
    if None not in (result.ma20, result.ma50, result.ma200):
        if result.ma20 > result.ma50 > result.ma200:
            score += 25
            reasons.append("MA hizalaması güçlü pozitif")
        elif result.ma20 > result.ma50:
            score += 18
            reasons.append("MA kısa-orta pozitif")
        elif result.ma20 < result.ma50 < result.ma200:
            score += 3
            reasons.append("MA hizalaması negatif")
        else:
            score += 10
            reasons.append("MA karışık")
    else:
        score += 8
        reasons.append("MA verisi eksik")

    # 3) Price vs MA20/50/200 (0-20)
    pma = 0
    if result.price is not None and result.ma20 is not None and result.price > result.ma20:
        pma += 7
    if result.price is not None and result.ma50 is not None and result.price > result.ma50:
        pma += 6
    if result.price is not None and result.ma200 is not None and result.price > result.ma200:
        pma += 7
    score += pma
    reasons.append(f"Fiyat/MA skoru: {pma}/20")

    # 4) MACD (0-20)
    if result.macd is None or result.macd_signal is None:
        score += 8
        reasons.append("MACD verisi sınırlı")
    elif result.macd > result.macd_signal:
        macd_points = 14
        if (result.macd_hist or 0) > 0:
            macd_points += 6
            reasons.append("MACD bullish + pozitif histogram")
        else:
            reasons.append("MACD bullish")
        score += macd_points
    else:
        macd_points = 4
        if (result.macd_hist or 0) < 0:
            macd_points = 2
            reasons.append("MACD bearish + negatif histogram")
        else:
            reasons.append("MACD bearish")
        score += macd_points

    # 5) Volume (0-15)
    vol_points = 7
    if result.is_volume_spike:
        if result.change_pct is not None and result.change_pct >= 0:
            vol_points = 15
            reasons.append("Hacim spike + yukarı momentum")
        elif result.change_pct is not None and result.change_pct < 0:
            vol_points = 3
            reasons.append("Hacim spike + aşağı baskı")
        else:
            vol_points = 10
            reasons.append("Hacim spike")
    else:
        ratio = result.volume_ratio
        if ratio is not None and ratio >= 1.2:
            vol_points = 11
            reasons.append("Hacim ortalamanın üstünde")
        elif ratio is not None and ratio < 0.8:
            vol_points = 5
            reasons.append("Hacim zayıf")
        else:
            reasons.append("Hacim normal")
    score += vol_points

    score = max(0, min(100, int(round(score))))
    return ScoreResult(
        symbol=result.symbol,
        score=score,
        signal=_signal_label(score),
        strength=_strength(score),
        reasons=reasons,
    )


def score_symbol(raw_symbol: str) -> ScoreResult | None:
    symbol = normalize_symbol(raw_symbol)
    result = analyze(symbol)
    if result is None:
        return None
    return score_analysis(result)


def rank_symbols(symbols: list[str]) -> list[ScoreResult]:
    ranked: list[ScoreResult] = []
    seen: set[str] = set()
    for sym in symbols:
        normalized = normalize_symbol(sym)
        if normalized in seen:
            continue
        seen.add(normalized)

        result = analyze(normalized)
        if result is None:
            continue
        ranked.append(score_analysis(result))

    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked


def scan_top_stocks(symbols: list[str], top_n: int = 10, max_symbols: int = 30) -> list[ScoreResult]:
    """Analyze a bounded symbol list and return top ranked stocks by score."""
    ranked: list[ScoreResult] = []
    seen: set[str] = set()

    for sym in symbols:
        normalized = normalize_symbol(sym)
        if normalized in seen:
            continue
        seen.add(normalized)
        if len(seen) > max_symbols:
            break

        try:
            result = analyze(normalized)
        except Exception as exc:
            # Keep scan resilient: one malformed symbol should never break the entire request.
            logger.warning("scan_top_stocks: analyze failed for symbol=%s error=%s", normalized, exc)
            continue
        if result is None:
            logger.debug("scan_top_stocks: %s returned no analysis", normalized)
            continue

        try:
            scored = score_analysis(result)
        except Exception as exc:
            logger.warning("scan_top_stocks: score_analysis failed for symbol=%s error=%s", normalized, exc)
            continue
        logger.debug(
            "scan_top_stocks: %s -> score=%s signal=%s strength=%s",
            scored.symbol,
            scored.score,
            scored.signal,
            scored.strength,
        )
        ranked.append(scored)

    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked[:top_n]
