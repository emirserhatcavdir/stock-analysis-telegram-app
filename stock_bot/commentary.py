"""Narrative commentary builders for symbol and list insights."""

from __future__ import annotations

from dataclasses import dataclass

from stock_bot.analysis import analyze
from stock_bot.fundamentals import get_fundamentals
from stock_bot.scoring import score_symbol


@dataclass
class CommentaryResult:
    title: str
    body_lines: list[str]

    def format_text(self) -> str:
        return "\n".join([self.title, "", *self.body_lines])


def _signal_bias(score: int | None) -> str:
    if score is None:
        return "belirsiz"
    if score >= 70:
        return "pozitif"
    if score >= 55:
        return "olumluya yakin"
    if score >= 45:
        return "notr"
    if score >= 30:
        return "zayif"
    return "negatif"


def _risk_text(beta: float | None, atr_pct: float | None) -> str:
    parts: list[str] = []
    if beta is not None:
        if beta >= 1.3:
            parts.append("beta yuksek")
        elif beta <= 0.8:
            parts.append("beta gorece dusuk")
    if atr_pct is not None:
        if atr_pct >= 4:
            parts.append("oynaklik yuksek")
        elif atr_pct <= 2:
            parts.append("oynaklik gorece sakin")
    return ", ".join(parts) if parts else "risk seviyesi notr"


def build_symbol_commentary(symbol: str) -> CommentaryResult | None:
    analysis = analyze(symbol)
    score = score_symbol(symbol)
    fundamentals = get_fundamentals(symbol)

    if analysis is None and score is None and fundamentals is None:
        return None

    score_value = score.score if score is not None else None
    signal_bias = _signal_bias(score_value)

    lines: list[str] = []
    if analysis is not None:
        change = analysis.change_pct
        if change is None:
            lines.append("Gunluk fiyat yonu icin yeterli veri yok.")
        elif change >= 0:
            lines.append(f"Gunluk hareket pozitif ({change:+.2f}%).")
        else:
            lines.append(f"Gunluk hareket negatif ({change:+.2f}%).")

        lines.append(f"Teknik tarafta ana gorunum: {analysis.trend}.")
        lines.append(f"RSI durumu: {analysis.rsi_label}; genel sinyal dengesi {signal_bias}.")
        lines.append(f"Volatilite/risk yorumu: {_risk_text(fundamentals.beta if fundamentals else None, analysis.atr_pct)}.")

    if fundamentals is not None:
        pe_text = f"F/K {fundamentals.pe_trailing:.2f}" if fundamentals.pe_trailing is not None else "F/K n/a"
        pb_text = f"PD/DD {fundamentals.pb:.2f}" if fundamentals.pb is not None else "PD/DD n/a"
        roe_text = (
            f"ROE {fundamentals.roe * 100:.2f}%" if fundamentals.roe is not None else "ROE n/a"
        )
        lines.append(f"Temel metrikler: {pe_text}, {pb_text}, {roe_text}.")
        lines.append(f"Temel kalite etiketi: {fundamentals.quality_label()}.")

    if score is not None:
        lines.append(f"Model skoru: {score.score}/100 ({score.strength}).")

    lines.append("Not: Bu cikti yatirim tavsiyesi degildir; risk yonetimi ve stop-planiyla birlikte degerlendirilmelidir.")

    return CommentaryResult(title=f"*{symbol} Yorum*", body_lines=lines)


def build_group_commentary(symbols: list[str], label: str) -> CommentaryResult | None:
    if not symbols:
        return None

    scored_rows = []
    for s in symbols:
        scored = score_symbol(s)
        if scored is None:
            continue
        scored_rows.append(scored)

    if not scored_rows:
        return CommentaryResult(
            title=f"*{label} Yorum*",
            body_lines=["Yeterli skor verisi olusmadi."],
        )

    scored_rows.sort(key=lambda x: x.score, reverse=True)
    avg = sum(r.score for r in scored_rows) / len(scored_rows)
    best = scored_rows[0]
    weak = scored_rows[-1]

    bias = _signal_bias(round(avg))
    lines = [
        f"Genel sinyal ortalamasi: {avg:.1f}/100 ({bias}).",
        f"One cikan: {best.symbol} ({best.score}/100, {best.strength}).",
        f"Zayif halka: {weak.symbol} ({weak.score}/100, {weak.strength}).",
        "Skor dagilimi yakin ise secicilik artirilmali, dagilim acik ise guclu-zayif ayrimi daha net kabul edilebilir.",
        "Not: Bu cikti yatirim tavsiyesi degildir.",
    ]
    return CommentaryResult(title=f"*{label} Yorum*", body_lines=lines)