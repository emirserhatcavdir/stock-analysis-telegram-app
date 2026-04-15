"""Technical analysis: yfinance download, RSI, Moving Averages, signals."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import RLock
from typing import Any

import pandas as pd
import yfinance as yf

from stock_bot.config import (
    MA_LONG,
    MA_MID,
    MA_SHORT,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    RSI_PERIOD,
)

logger = logging.getLogger(__name__)

_history_cache_lock = RLock()
_history_cache: dict[tuple[str, str], tuple[float, pd.DataFrame]] = {}


# ── Helpers ───────────────────────────────────────────────────

def normalize_symbol(raw: str) -> str:
    s = raw.strip().upper()
    if s and "." not in s:
        s += ".IS"
    return s


def fmt(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{decimals}f}"


def _history_ttl_seconds(period: str) -> int:
    key = period.strip().lower()
    if key in {"1d", "5d"}:
        return 20
    if key in {"1mo", "3mo", "6mo"}:
        return 90
    return 180


def download_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    """Download daily OHLCV from yfinance with MultiIndex fix."""
    cache_key = (symbol, period)
    now = time.time()
    with _history_cache_lock:
        cached = _history_cache.get(cache_key)
        if cached is not None:
            expires_at, cached_df = cached
            if expires_at > now:
                return cached_df.copy()

    try:
        df = yf.download(
            symbol,
            period=period,
            interval="1d",
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        ttl = _history_ttl_seconds(period)
        with _history_cache_lock:
            _history_cache[cache_key] = (now + ttl, df.copy())
        return df
    except Exception:
        logger.exception("yfinance download failed: %s", symbol)
        return pd.DataFrame()


# ── Indicators ────────────────────────────────────────────────

def compute_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def compute_moving_averages(
    close: pd.Series,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    return (
        close.rolling(window=MA_SHORT).mean(),
        close.rolling(window=MA_MID).mean(),
        close.rolling(window=MA_LONG).mean(),
    )


def compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def compute_bollinger(
    close: pd.Series,
    period: int = 20,
    std_mult: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = mid + (std_mult * std)
    lower = mid - (std_mult * std)
    return upper, mid, lower


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window=period, min_periods=period).mean()


def detect_volume_spike(
    volume: pd.Series,
    lookback: int = 20,
    multiplier: float = 1.8,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    vol_ma = volume.rolling(window=lookback, min_periods=lookback).mean()
    ratio = volume / vol_ma.replace(0, pd.NA)
    is_spike = ratio >= multiplier
    return is_spike.fillna(False), ratio, vol_ma


# ── Analysis result ───────────────────────────────────────────

@dataclass
class AnalysisResult:
    symbol: str
    price: float | None
    change_pct: float | None  # daily % change
    rsi: float | None
    ma20: float | None
    ma50: float | None
    ma200: float | None
    macd: float | None
    macd_signal: float | None
    macd_hist: float | None
    bb_upper: float | None
    bb_mid: float | None
    bb_lower: float | None
    atr: float | None
    atr_pct: float | None
    volume_avg20: float | None
    volume_ratio: float | None
    is_volume_spike: bool
    volume: float | None
    high_52w: float | None
    low_52w: float | None
    period: str = "1y"
    history_points: int = 0
    score: int | None = None
    score_signal: str | None = None
    score_breakdown: list[str] | None = None

    @property
    def ma_availability_note(self) -> str | None:
        if self.ma20 is not None and self.ma50 is not None and self.ma200 is not None:
            return None

        points = int(self.history_points or 0)
        if points < MA_SHORT:
            return (
                f"MA verisi yetersiz: {points} gunluk kapanis var; "
                f"MA{MA_SHORT}/MA{MA_MID}/MA{MA_LONG} icin en az {MA_LONG} gunluk veri gerekir."
            )
        if points < MA_MID:
            return (
                f"MA{MA_MID}/MA{MA_LONG} hesaplanamadi: {points} gunluk veri var, "
                f"en az {MA_LONG} gunluk veri gerekir."
            )
        if points < MA_LONG:
            return (
                f"MA{MA_LONG} hesaplanamadi: {points} gunluk veri var, "
                f"en az {MA_LONG} gunluk veri gerekir."
            )
        return "MA degerleri eksik veya gecersiz; veri kaynagi son barlarda bos deger dondurmus olabilir."

    @property
    def rsi_label(self) -> str:
        if self.rsi is None:
            return "n/a"
        if self.rsi >= RSI_OVERBOUGHT:
            return "overbought 🔥"
        if self.rsi <= RSI_OVERSOLD:
            return "oversold 💎"
        return "neutral"

    @property
    def rsi_state(self) -> str:
        if self.rsi is None:
            return "neutral"
        if self.rsi >= RSI_OVERBOUGHT:
            return "overbought"
        if self.rsi <= RSI_OVERSOLD:
            return "oversold"
        return "neutral"

    @property
    def trend(self) -> str:
        """Stronger trend label using MA alignment + MACD confirmation."""
        state = _classify_trend_state(
            self.price,
            self.ma20,
            self.ma50,
            self.ma200,
            self.macd,
            self.macd_signal,
        )
        if state == "unknown":
            return "Veri yetersiz (MA trendi hesaplanamadi)"
        if state == "strong_up":
            return "📈 Güçlü yükseliş"
        if state == "strong_down":
            return "📉 Güçlü düşüş"
        if state == "up":
            return "📈 Yükseliş"
        if state == "down":
            return "📉 Düşüş"
        return "➡️ Yatay"

    @property
    def macd_label(self) -> str:
        if self.macd is None or self.macd_signal is None:
            return "n/a"
        if self.macd > self.macd_signal and (self.macd_hist or 0) >= 0:
            return "bullish"
        if self.macd < self.macd_signal and (self.macd_hist or 0) <= 0:
            return "bearish"
        return "neutral"

    @property
    def band_state(self) -> str:
        if self.price is None or self.bb_upper is None or self.bb_lower is None:
            return "n/a"
        if self.price >= self.bb_upper:
            return "üst banda yakın/üstünde"
        if self.price <= self.bb_lower:
            return "alt banda yakın/altında"
        return "band içinde"

    def _period_context(self) -> str:
        mapping = {
            "1mo": "Kısa vade (1A)",
            "3mo": "Kısa-orta vade (3A)",
            "6mo": "Orta vade (6A)",
            "1y": "Uzun vade (1Y)",
            "2y": "Uzun vade (2Y)",
        }
        key = str(self.period or "1y").strip().lower()
        return mapping.get(key, f"Seçili dönem ({key})")

    def _signal_bias(self) -> str:
        trend_state = _classify_trend_state(
            self.price,
            self.ma20,
            self.ma50,
            self.ma200,
            self.macd,
            self.macd_signal,
        )
        if trend_state in {"strong_up", "up"} and self.macd_label == "bullish":
            return "bullish"
        if trend_state in {"strong_down", "down"} and self.macd_label == "bearish":
            return "bearish"
        return "neutral"

    @property
    def commentary(self) -> str:
        context = self._period_context()
        ma_text = "MA yapısı için veri sınırlı"
        if self.ma20 is not None and self.ma50 is not None and self.ma200 is not None and self.price is not None:
            if self.price > self.ma200 and self.ma20 > self.ma50 > self.ma200:
                ma_text = "fiyat ve MA dizilimi yukarı trendi destekliyor"
            elif self.price < self.ma200 and self.ma20 < self.ma50 < self.ma200:
                ma_text = "fiyat ve MA dizilimi aşağı trend baskısını gösteriyor"
            elif self.ma20 > self.ma50:
                ma_text = "kısa vadeli ortalamalar yukarı eğilimli ancak uzun vadede teyit sınırlı"
            else:
                ma_text = "hareketli ortalamalar karışık ve net bir yön teyidi üretmiyor"

        if self.rsi is None:
            rsi_text = "RSI verisi yetersiz"
        elif self.rsi <= RSI_OVERSOLD:
            rsi_text = f"RSI {self.rsi:.1f} ile aşırı satım bölgesinde"
        elif self.rsi >= RSI_OVERBOUGHT:
            rsi_text = f"RSI {self.rsi:.1f} ile aşırı alım bölgesinde"
        else:
            rsi_text = f"RSI {self.rsi:.1f} ile nötr bölgede"

        if self.macd is None or self.macd_signal is None:
            macd_text = "MACD teyidi sınırlı"
        elif self.macd > self.macd_signal and (self.macd_hist or 0) >= 0:
            macd_text = "MACD momentum tarafında pozitif"
        elif self.macd > self.macd_signal:
            macd_text = "MACD pozitif bölgede ancak momentum zayıf"
        elif self.macd < self.macd_signal and (self.macd_hist or 0) <= 0:
            macd_text = "MACD aşağı yönlü momentumu doğruluyor"
        else:
            macd_text = "MACD negatif bölgede fakat zayıflama sinyali var"

        extra = ""
        if self.ma_availability_note:
            extra = f" {self.ma_availability_note}"

        return f"{context} görünümünde {ma_text}. {rsi_text}; {macd_text}.{extra}".strip()

    @property
    def signal_summary(self) -> str:
        context = self._period_context()
        bias = self._signal_bias()

        if bias == "bullish":
            direction = "Bullish"
            reason = "trend ve MACD aynı yönde pozitif"
        elif bias == "bearish":
            direction = "Bearish"
            reason = "trend ve MACD aynı yönde negatif"
        else:
            direction = "Neutral"
            reason = "göstergeler karışık, net yön teyidi sınırlı"

        rsi_note = "RSI n/a"
        if self.rsi is not None:
            if self.rsi <= RSI_OVERSOLD:
                rsi_note = f"RSI {self.rsi:.1f} (oversold)"
            elif self.rsi >= RSI_OVERBOUGHT:
                rsi_note = f"RSI {self.rsi:.1f} (overbought)"
            else:
                rsi_note = f"RSI {self.rsi:.1f} (neutral)"

        return f"{context}: {direction} sinyal; {reason}. {rsi_note}."

    def format_text(self) -> str:
        change_str = ""
        if self.change_pct is not None:
            arrow = "🟢" if self.change_pct >= 0 else "🔴"
            change_str = f" ({arrow} {self.change_pct:+.2f}%)"

        lines = [
            f"*{self.symbol}*",
            f"💰 Fiyat: {fmt(self.price)} TL{change_str}",
            f"🏁 Skor: {self.score if self.score is not None else 'n/a'} ({self.score_signal or 'n/a'})",
            f"📊 RSI({RSI_PERIOD}): {fmt(self.rsi)} — {self.rsi_label}",
            f"📈 MA{MA_SHORT}: {fmt(self.ma20)} | MA{MA_MID}: {fmt(self.ma50)} | MA{MA_LONG}: {fmt(self.ma200)}",
            f"🧲 MACD: {fmt(self.macd, 3)} | Signal: {fmt(self.macd_signal, 3)} | Hist: {fmt(self.macd_hist, 3)} ({self.macd_label})",
            f"📉 Bollinger(20,2): Üst {fmt(self.bb_upper)} | Orta {fmt(self.bb_mid)} | Alt {fmt(self.bb_lower)} ({self.band_state})",
            f"📏 ATR(14): {fmt(self.atr)} TL ({fmt(self.atr_pct)}%)",
            f"📦 Hacim: {fmt(self.volume, 0)} | Ort20: {fmt(self.volume_avg20, 0)} | Oran: {fmt(self.volume_ratio, 2)} {'(SPIKE)' if self.is_volume_spike else ''}",
            f"📉 52H Düşük: {fmt(self.low_52w)}  |  52H Yüksek: {fmt(self.high_52w)}",
            f"🧭 Trend: {self.trend}",
            f"🎯 Sinyal Özeti: {self.signal_summary}",
        ]
        return "\n".join(lines)

    def _ma_trend_text(self) -> str:
        if None in (self.ma20, self.ma50, self.ma200):
            return "n/a"
        if self.ma20 > self.ma50 > self.ma200:
            return "Bullish alignment"
        if self.ma20 < self.ma50 < self.ma200:
            return "Bearish alignment"
        if self.ma20 > self.ma50:
            return "Short-term bullish"
        return "Mixed"

    def _bollinger_position_text(self) -> str:
        if self.price is None or self.bb_upper is None or self.bb_lower is None:
            return "n/a"
        if self.price > self.bb_upper:
            return "above_upper"
        if self.price < self.bb_lower:
            return "below_lower"
        return "inside"

    def _risk_profile(self) -> tuple[str, str]:
        score = int(self.score or 0)
        atr_pct = self.atr_pct or 0.0
        if score >= 70 and atr_pct < 3.0:
            return "Low", "Signal quality is strong and volatility is controlled."
        if score < 40 or atr_pct >= 5.0:
            return "High", "Weak signal profile and/or elevated volatility increases downside risk."
        return "Medium", "Mixed indicators or moderate volatility suggest balanced risk-reward."

    def _commentary(self) -> str:
        signal = str(self.score_signal or "neutral").replace("_", " ").title()
        trend = self._ma_trend_text()
        macd = self.macd_label.title()
        bb_pos = self._bollinger_position_text()
        vol = "volume participation is elevated" if self.is_volume_spike else "volume is not confirming strongly"
        return (
            f"{trend} structure with {macd} MACD tone. Price is {bb_pos} relative to Bollinger bands and {vol}. "
            f"Current signal is {signal}, indicating {'short-term opportunity' if signal in {'Strong Buy', 'Buy'} else 'possible weakness'} in momentum."
        )

    def _summary(self) -> str:
        signal = str(self.score_signal or "neutral").replace("_", " ").title()
        score = int(self.score or 0)
        if signal in {"Strong Buy", "Buy"}:
            return f"Bias remains constructive with score {score}/100; pullback entries can be considered with risk controls."
        if signal == "Sell":
            return f"Setup remains defensive with score {score}/100; capital protection should be prioritized."
        return f"Setup is balanced with score {score}/100; confirmation is needed before directional commitment."

    def format_professional_report(self) -> str:
        risk_level, risk_text = self._risk_profile()
        breakdown = self.score_breakdown or []
        breakdown_text = " | ".join(breakdown[:5]) if breakdown else "Score components unavailable"

        lines = [
            f"*{self.symbol} Analysis*",
            f"Price: {fmt(self.price)} TL | Score: {self.score if self.score is not None else 'n/a'} | Signal: {str(self.score_signal or 'n/a').replace('_', ' ').title()}",
            f"RSI: {fmt(self.rsi)} | MA Trend: {self._ma_trend_text()} | MACD: {self.macd_label.title()}",
            f"Bollinger: {self._bollinger_position_text()} | Volume Spike: {'Yes' if self.is_volume_spike else 'No'}",
            "",
            "*Comment*",
            self._commentary(),
            "",
            "*Risk*",
            f"{risk_level} - {risk_text}",
            "",
            "*Score Breakdown*",
            breakdown_text,
            "",
            "*Summary*",
            self._summary(),
        ]
        return "\n".join(lines)


def _safe(val: Any) -> float | None:
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _classify_trend_state(
    price: float | None,
    ma20: float | None,
    ma50: float | None,
    ma200: float | None,
    macd: float | None,
    macd_signal: float | None,
) -> str:
    if price is None or ma20 is None or ma50 is None or ma200 is None:
        return "unknown"

    bullish_ma = price > ma200 and ma20 > ma50 > ma200
    bearish_ma = price < ma200 and ma20 < ma50 < ma200
    macd_bull = macd is not None and macd_signal is not None and macd > macd_signal
    macd_bear = macd is not None and macd_signal is not None and macd < macd_signal

    if bullish_ma and macd_bull:
        return "strong_up"
    if bearish_ma and macd_bear:
        return "strong_down"
    if ma20 > ma50:
        return "up"
    if ma20 < ma50:
        return "down"
    return "sideways"


def _last_valid_value(series: pd.Series) -> float | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return _safe(valid.iloc[-1])


def calculate_macd_indicator(close: pd.Series) -> dict[str, float | str | None]:
    """Return MACD summary structure for the latest bar using pandas EMA."""
    macd_line, signal_line, histogram = compute_macd(close, fast=12, slow=26, signal=9)

    macd_value = _last_valid_value(macd_line)
    signal_value = _last_valid_value(signal_line)
    histogram_value = _last_valid_value(histogram)

    trend = "bearish"
    if macd_value is not None and signal_value is not None and macd_value >= signal_value:
        trend = "bullish"

    return {
        "macd": macd_value,
        "signal": signal_value,
        "histogram": histogram_value,
        "trend": trend,
    }


def calculate_bollinger_bands(close: pd.Series) -> dict[str, float | str | None]:
    """Return Bollinger Bands summary using 20-period MA and 2*std."""
    upper, middle, lower = compute_bollinger(close, period=20, std_mult=2.0)

    upper_value = _last_valid_value(upper)
    middle_value = _last_valid_value(middle)
    lower_value = _last_valid_value(lower)
    price_value = _last_valid_value(close)

    position = "inside"
    if price_value is not None and upper_value is not None and lower_value is not None:
        if price_value > upper_value:
            position = "above_upper"
        elif price_value < lower_value:
            position = "below_lower"

    return {
        "upper": upper_value,
        "middle": middle_value,
        "lower": lower_value,
        "position": position,
    }


def calculate_score(indicators: dict[str, Any]) -> dict[str, Any]:
    """Score indicators into 0-100 and map to trading signal.

    Expected keys are the normalized indicator names used by analyze():
    rsi, ma20, ma50, ma200, macd, signal, histogram, bb_upper, bb_middle,
    bb_lower, position, volume_ratio, volume_spike, price.
    Backward-compatible aliases are also accepted.
    """

    def _num(*names: str) -> float | None:
        for name in names:
            value = indicators.get(name)
            if value is None:
                continue
            try:
                if pd.isna(value):
                    continue
            except (TypeError, ValueError):
                pass
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    rsi = _num("rsi", "rsi_value")
    ma20 = _num("ma20")
    ma50 = _num("ma50")
    ma200 = _num("ma200")
    price = _num("price")
    macd = _num("macd", "macd_line")
    macd_signal = _num("signal", "macd_signal")
    macd_hist = _num("histogram", "macd_hist", "macd_histogram")

    trend_state = str(indicators.get("trend_state", "unknown")).strip().lower()
    if trend_state not in {"strong_up", "up", "sideways", "down", "strong_down", "unknown"}:
        trend_state = "unknown"

    # Center score to reduce neutral crowding and allow negative evidence to pull it down.
    score = 50
    components: list[str] = []

    logger.debug(
        "calculate_score inputs: symbol=%s rsi=%s ma20=%s ma50=%s ma200=%s price=%s macd=%s macd_signal=%s macd_hist=%s trend_state=%s",
        indicators.get("symbol", "unknown"),
        rsi,
        ma20,
        ma50,
        ma200,
        price,
        macd,
        macd_signal,
        macd_hist,
        trend_state,
    )

    components.append(f"BASE:{score}")

    def _apply_delta(label: str, delta: int) -> None:
        nonlocal score
        score += delta
        components.append(f"{label}:{delta:+d}")

    def _soft_cap(value: int, lower: int = 15, upper: int = 85) -> int:
        return max(lower, min(upper, value))

    # 1) RSI contribution (symmetric around 40-60 neutral zone)
    if rsi is None:
        components.append("RSI:+0 (missing)")
    elif rsi <= 30:
        _apply_delta("RSI", 8)
        components.append("(oversold)")
    elif rsi <= 40:
        _apply_delta("RSI", 4)
        components.append("(supportive)")
    elif rsi < 60:
        components.append("RSI:+0 (neutral zone)")
    elif rsi < 70:
        _apply_delta("RSI", -4)
        components.append("(elevated)")
    else:
        _apply_delta("RSI", -8)
        components.append("(overbought)")

    # 2) MA/price structure contribution
    if None not in (ma20, ma50, ma200):
        if price is not None and price > ma200 and ma20 > ma50 > ma200:
            _apply_delta("MA", 10)
            components.append("(full bullish alignment)")
        elif price is not None and price > ma200 and ma20 > ma50:
            _apply_delta("MA", 6)
            components.append("(bullish)")
        elif price is not None and price < ma200 and ma20 < ma50 < ma200:
            _apply_delta("MA", -10)
            components.append("(full bearish alignment)")
        elif price is not None and price < ma200 and ma20 < ma50:
            _apply_delta("MA", -6)
            components.append("(bearish)")
        elif ma20 > ma50:
            _apply_delta("MA", 4)
            components.append("(short-term up)")
        elif ma20 < ma50:
            _apply_delta("MA", -4)
            components.append("(short-term down)")
        else:
            components.append("MA:+0 (mixed)")
    else:
        components.append("MA:+0 (missing)")

    # 3) Trend-state contribution
    if trend_state == "strong_up":
        _apply_delta("TREND", 4)
        components.append("(strong_up)")
    elif trend_state == "up":
        _apply_delta("TREND", 2)
        components.append("(up)")
    elif trend_state == "strong_down":
        _apply_delta("TREND", -4)
        components.append("(strong_down)")
    elif trend_state == "down":
        _apply_delta("TREND", -2)
        components.append("(down)")
    else:
        components.append("TREND:+0")

    # 4) MACD contribution
    if macd is None or macd_signal is None:
        components.append("MACD:+0 (missing)")
    elif macd > macd_signal:
        if macd_hist is None or macd_hist >= 0:
            _apply_delta("MACD", 6)
            components.append("(bullish confirmed)")
        else:
            _apply_delta("MACD", 3)
            components.append("(bullish weak)")
    elif macd < macd_signal:
        if macd_hist is None or macd_hist <= 0:
            _apply_delta("MACD", -6)
            components.append("(bearish confirmed)")
        else:
            _apply_delta("MACD", -3)
            components.append("(bearish weak)")
    else:
        components.append("MACD:+0 (flat)")

    score = int(round(_soft_cap(score)))

    if score >= 70:
        signal = "strong_buy"
    elif score >= 56:
        signal = "buy"
    elif score >= 44:
        signal = "neutral"
    else:
        signal = "sell"

    logger.debug(
        "calculate_score(%s): score=%s signal=%s | %s",
        indicators.get("symbol", "unknown"),
        score,
        signal,
        " ; ".join(components),
    )

    return {
        "score": score,
        "signal": signal,
        "components": components,
    }


def analyze(symbol: str, period: str = "1y") -> AnalysisResult | None:
    """Run full analysis on *symbol* and return an AnalysisResult."""
    df = download_history(symbol, period=period)
    if df.empty or "Close" not in df.columns:
        return None

    close = df["Close"].astype(float)
    close_non_null = close.dropna()
    if len(close_non_null) < 2:
        return None

    high = df["High"].astype(float) if "High" in df.columns else close
    low = df["Low"].astype(float) if "Low" in df.columns else close

    ma20, ma50, ma200 = compute_moving_averages(close)
    rsi = compute_rsi(close)
    macd_summary = calculate_macd_indicator(close)
    bb_summary = calculate_bollinger_bands(close)
    atr = compute_atr(high, low, close)

    last_idx = close_non_null.index[-1]
    prev_idx = close_non_null.index[-2]

    price = _safe(close.loc[last_idx])
    prev = _safe(close.loc[prev_idx])
    change_pct = None
    if price is not None and prev is not None and prev != 0:
        change_pct = ((price - prev) / prev) * 100

    if "Volume" in df.columns:
        vol_series = df["Volume"].astype(float)
        vol = _last_valid_value(vol_series)
        vol_spike_series, vol_ratio_series, vol_ma_series = detect_volume_spike(vol_series)
        vol_spike_valid = vol_spike_series.dropna()
        vol_ratio_valid = vol_ratio_series.dropna()
        vol_ma_valid = vol_ma_series.dropna()
        is_vol_spike = bool(vol_spike_valid.iloc[-1]) if len(vol_spike_valid) else False
        vol_ratio = _safe(vol_ratio_valid.iloc[-1]) if len(vol_ratio_valid) else None
        vol_ma20 = _safe(vol_ma_valid.iloc[-1]) if len(vol_ma_valid) else None
    else:
        vol = None
        is_vol_spike = False
        vol_ratio = None
        vol_ma20 = None

    atr_last = _last_valid_value(atr)
    atr_pct = None
    if atr_last is not None and price is not None and price != 0:
        atr_pct = (atr_last / price) * 100

    score_summary = calculate_score(
        {
            "symbol": symbol,
            "rsi": _last_valid_value(rsi),
            "ma20": _last_valid_value(ma20),
            "ma50": _last_valid_value(ma50),
            "ma200": _last_valid_value(ma200),
            "price": price,
            "macd": macd_summary["macd"],
            "signal": macd_summary["signal"],
            "histogram": macd_summary["histogram"],
            "trend_state": _classify_trend_state(
                price,
                _last_valid_value(ma20),
                _last_valid_value(ma50),
                _last_valid_value(ma200),
                macd_summary["macd"],
                macd_summary["signal"],
            ),
            "bb_upper": bb_summary["upper"],
            "bb_middle": bb_summary["middle"],
            "bb_lower": bb_summary["lower"],
            "position": bb_summary["position"],
            "volume_ratio": vol_ratio,
            "volume_spike": is_vol_spike,
        }
    )

    logger.debug(
        "analyze(%s): price=%s rsi=%s ma20=%s ma50=%s ma200=%s macd=%s signal=%s hist=%s bb_pos=%s vol_ratio=%s spike=%s score=%s",
        symbol,
        price,
        _last_valid_value(rsi),
        _last_valid_value(ma20),
        _last_valid_value(ma50),
        _last_valid_value(ma200),
        macd_summary["macd"],
        macd_summary["signal"],
        macd_summary["histogram"],
        bb_summary["position"],
        vol_ratio,
        is_vol_spike,
        score_summary["score"],
    )

    return AnalysisResult(
        symbol=symbol,
        price=price,
        change_pct=change_pct,
        rsi=_last_valid_value(rsi),
        ma20=_last_valid_value(ma20),
        ma50=_last_valid_value(ma50),
        ma200=_last_valid_value(ma200),
        macd=macd_summary["macd"],
        macd_signal=macd_summary["signal"],
        macd_hist=macd_summary["histogram"],
        bb_upper=bb_summary["upper"],
        bb_mid=bb_summary["middle"],
        bb_lower=bb_summary["lower"],
        atr=atr_last,
        atr_pct=atr_pct,
        volume_avg20=vol_ma20,
        volume_ratio=vol_ratio,
        is_volume_spike=is_vol_spike,
        volume=vol,
        high_52w=_safe(close.max()),
        low_52w=_safe(close.min()),
        period=period,
        history_points=int(len(close_non_null)),
        score=int(score_summary["score"]),
        score_signal=str(score_summary["signal"]),
        score_breakdown=list(score_summary.get("components", [])),
    )


def get_current_price(symbol: str) -> float | None:
    """Quick price fetch (shorter history)."""
    df = download_history(symbol, period="5d")
    if df.empty or "Close" not in df.columns:
        return None
    return _safe(df["Close"].iloc[-1])
