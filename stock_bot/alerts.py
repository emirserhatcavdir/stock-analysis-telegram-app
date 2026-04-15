"""Alert engine for user-scoped price/RSI/MA/volume notifications."""

from __future__ import annotations

import logging
import time
from typing import Any

from telegram.ext import ContextTypes

from stock_bot.analysis import AnalysisResult, analyze
from stock_bot.scoring import score_analysis
from stock_bot.data_manager import (
    get_chat_advanced_alerts,
    get_chat_alerts,
    get_chat_alert_runtime_state,
    get_chat_signal_state,
    load_portfolio,
    set_chat_advanced_alerts,
    set_chat_alert_runtime_state,
    set_chat_signal_state,
)

logger = logging.getLogger(__name__)


def _within_cooldown(rule: dict[str, Any], now_ts: float) -> bool:
    cooldown = int(rule.get("cooldown", 3600) or 3600)
    last_triggered = float(rule.get("last_triggered", 0) or 0)
    return now_ts - last_triggered < cooldown


def _mark_triggered(rule: dict[str, Any], now_ts: float) -> None:
    rule["last_triggered"] = now_ts


def _normalize_signal_name(raw: str) -> str:
    text = str(raw or "").strip().lower().replace(" ", "_")
    if text in {"strongbuy", "strong_buy"}:
        return "strong_buy"
    if text in {"buy"}:
        return "buy"
    if text in {"neutral"}:
        return "neutral"
    if text in {"sell"}:
        return "sell"
    return text


def _analysis_score_and_signal(result: AnalysisResult) -> tuple[int, str]:
    if result.score is not None and result.score_signal:
        return int(result.score), _normalize_signal_name(result.score_signal)

    scored = score_analysis(result)
    return int(scored.score), _normalize_signal_name(scored.signal)


def evaluate_rsi(
    symbol: str,
    result: AnalysisResult,
    rule: dict[str, Any],
    signal_state: dict[str, str],
) -> tuple[bool, str | None, bool]:
    """Evaluate RSI thresholds with transition-based duplicate prevention."""
    if result.rsi is None:
        return False, None, False

    side = str(rule.get("side") or "").lower().strip()
    try:
        threshold = float(rule.get("threshold") if rule.get("threshold") is not None else rule.get("target"))
    except (TypeError, ValueError):
        threshold = 70.0 if side != "below" else 30.0

    if side not in {"above", "below"}:
        state = str(rule.get("state", "")).lower().strip()
        if state in {"oversold", "below30"}:
            side = "below"
            threshold = 30.0 if rule.get("threshold") is None and rule.get("target") is None else threshold
        else:
            side = "above"
            threshold = 70.0 if rule.get("threshold") is None and rule.get("target") is None else threshold

    state_key = f"{symbol}:rsi:{side}:{threshold:.2f}"
    zone = "above" if result.rsi >= threshold else "below"
    prev_zone = signal_state.get(state_key, zone)

    state_changed = prev_zone != zone
    if state_changed:
        signal_state[state_key] = zone

    if zone == side and prev_zone != side:
        label = f"RSI above {threshold:.0f}" if side == "above" else f"RSI below {threshold:.0f}"
        message = f"📊 *{symbol}* {label} | RSI: {result.rsi:.2f}"
        return True, message, state_changed

    return False, None, state_changed


def evaluate_ma_crossover(
    symbol: str,
    result: AnalysisResult,
    rule: dict[str, Any],
    signal_state: dict[str, str],
) -> tuple[bool, str | None, bool]:
    """Evaluate MA50 > MA200 crossover with state tracking."""
    if result.ma50 is None or result.ma200 is None:
        return False, None, False

    state_key = f"{symbol}:ma50_gt_ma200"
    current_state = "above" if result.ma50 > result.ma200 else "below"
    prev_state = signal_state.get(state_key, current_state)

    direction = str(rule.get("direction", "golden")).lower().strip()
    target = "above" if direction in {"golden", "above"} else "below"

    state_changed = prev_state != current_state
    if state_changed:
        signal_state[state_key] = current_state

    if current_state == target and prev_state != target:
        if target == "above":
            message = f"📈 *{symbol}* MA crossover: MA50 > MA200"
        else:
            message = f"📉 *{symbol}* MA crossover: MA50 < MA200"
        return True, message, state_changed

    return False, None, state_changed


def evaluate_score_above(
    symbol: str,
    result: AnalysisResult,
    rule: dict[str, Any],
    signal_state: dict[str, str],
) -> tuple[bool, str | None, bool]:
    """Trigger when score crosses a threshold, once per crossing."""
    score, _ = _analysis_score_and_signal(result)
    side = str(rule.get("side") or "above").strip().lower()
    if side not in {"above", "below"}:
        side = "above"

    try:
        threshold = float(rule.get("threshold", rule.get("score", 80)) or 80)
    except (TypeError, ValueError):
        threshold = 80.0 if side == "above" else 45.0

    state_key = f"{symbol}:score:{side}:{threshold:.2f}"
    current_state = "above" if score >= threshold else "below"
    prev_state = signal_state.get(state_key, "below" if side == "above" else "above")
    state_changed = prev_state != current_state
    if state_changed:
        signal_state[state_key] = current_state

    if current_state == side and prev_state != side:
        if side == "above":
            message = f"🏁 *{symbol}* score threshold aşıldı: {score}/100 (eşik {threshold:.0f})"
        else:
            message = f"⚠️ *{symbol}* score threshold altına indi: {score}/100 (eşik {threshold:.0f})"
        return True, message, state_changed

    return False, None, state_changed


def evaluate_cross_event(
    symbol: str,
    result: AnalysisResult,
    rule: dict[str, Any],
    signal_state: dict[str, str],
) -> tuple[bool, str | None, bool]:
    condition = str(rule.get("condition") or "price_ma20").strip().lower()
    side = str(rule.get("side") or "above").strip().lower()
    if side not in {"above", "below"}:
        side = "above"

    left: float | None = None
    right: float | None = None
    label = "cross event"

    if condition == "price_ma20":
        left, right = result.price, result.ma20
        label = "Price vs MA20"
    elif condition == "price_ma50":
        left, right = result.price, result.ma50
        label = "Price vs MA50"
    elif condition == "ma20_ma50":
        left, right = result.ma20, result.ma50
        label = "MA20 vs MA50"
    else:
        return False, None, False

    if left is None or right is None:
        return False, None, False

    current_state = "above" if left >= right else "below"
    state_key = f"{symbol}:cross:{condition}"
    prev_state = signal_state.get(state_key, current_state)
    state_changed = prev_state != current_state
    if state_changed:
        signal_state[state_key] = current_state

    if current_state == side and prev_state != side:
        direction_text = "up" if side == "above" else "down"
        message = f"📉 *{symbol}* {label} cross {direction_text}"
        return True, message, state_changed

    return False, None, state_changed


def evaluate_signal_state(
    symbol: str,
    result: AnalysisResult,
    rule: dict[str, Any],
    signal_state: dict[str, str],
) -> tuple[bool, str | None, bool]:
    """Trigger when the score signal becomes the requested state."""
    score, current_signal = _analysis_score_and_signal(result)
    target = _normalize_signal_name(rule.get("signal", rule.get("state", "")))
    if target in {"strong_buy", "strongbuy"}:
        target = "strong_buy"

    if target not in {"strong_buy", "buy", "neutral", "sell"}:
        return False, None, False

    state_key = f"{symbol}:score_signal"
    prev_signal = signal_state.get(state_key, "")
    state_changed = prev_signal != current_signal
    if state_changed:
        signal_state[state_key] = current_signal

    if current_signal == target and prev_signal != target:
        pretty = target.replace("_", " ").title()
        message = f"🎯 *{symbol}* sinyal {pretty} oldu | Score: {score}/100"
        return True, message, state_changed

    return False, None, state_changed


async def check_alerts(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int,
    user_id: int,
) -> None:
    """Run one full alert scan for a user (called by scheduled job every X minutes)."""
    portfolio = load_portfolio(user_id)
    price_alerts = get_chat_alerts(user_id)
    adv_alerts = get_chat_advanced_alerts(user_id)
    runtime_state = get_chat_alert_runtime_state(user_id)

    all_symbols = sorted(set(portfolio.keys()) | set(price_alerts.keys()) | set(adv_alerts.keys()))
    if not all_symbols:
        return

    signal_state = get_chat_signal_state(user_id)
    signal_state_changed = False
    adv_changed = False
    runtime_changed = False
    now_ts = time.time()

    for symbol in all_symbols:
        result = analyze(symbol)
        if result is None:
            continue

        # Price above/below alerts (stateful crossing, anti-spam)
        rules = price_alerts.get(symbol, {})
        price = result.price
        if price is not None and isinstance(rules, dict):
            above = rules.get("above")
            below = rules.get("below")

            if above is not None and price >= float(above):
                key = f"price:{symbol}:above:{float(above):.4f}"
                state = runtime_state.get(key, {"fired": False, "condition_met": False, "last_triggered": 0.0, "last_reset": 0.0})
                prev_met = bool(state.get("condition_met", False))
                if not prev_met:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"🚀 *{symbol}* {float(above):.2f} TL ustune cikti! Guncel: {price:.2f} TL",
                        parse_mode="Markdown",
                    )
                    runtime_state[key] = {
                        "fired": True,
                        "condition_met": True,
                        "last_triggered": now_ts,
                        "last_reset": float(state.get("last_reset", 0) or 0),
                    }
                    runtime_changed = True
                else:
                    if not bool(state.get("fired", False)):
                        state["fired"] = True
                        runtime_state[key] = state
                        runtime_changed = True
            elif above is not None:
                key = f"price:{symbol}:above:{float(above):.4f}"
                state = runtime_state.get(key, {"fired": False, "condition_met": False, "last_triggered": 0.0, "last_reset": 0.0})
                if bool(state.get("condition_met", False)):
                    runtime_state[key] = {
                        "fired": False,
                        "condition_met": False,
                        "last_triggered": float(state.get("last_triggered", 0) or 0),
                        "last_reset": now_ts,
                    }
                    runtime_changed = True

            if below is not None and price <= float(below):
                key = f"price:{symbol}:below:{float(below):.4f}"
                state = runtime_state.get(key, {"fired": False, "condition_met": False, "last_triggered": 0.0, "last_reset": 0.0})
                prev_met = bool(state.get("condition_met", False))
                if not prev_met:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"📉 *{symbol}* {float(below):.2f} TL altina dustu! Guncel: {price:.2f} TL",
                        parse_mode="Markdown",
                    )
                    runtime_state[key] = {
                        "fired": True,
                        "condition_met": True,
                        "last_triggered": now_ts,
                        "last_reset": float(state.get("last_reset", 0) or 0),
                    }
                    runtime_changed = True
                else:
                    if not bool(state.get("fired", False)):
                        state["fired"] = True
                        runtime_state[key] = state
                        runtime_changed = True
            elif below is not None:
                key = f"price:{symbol}:below:{float(below):.4f}"
                state = runtime_state.get(key, {"fired": False, "condition_met": False, "last_triggered": 0.0, "last_reset": 0.0})
                if bool(state.get("condition_met", False)):
                    runtime_state[key] = {
                        "fired": False,
                        "condition_met": False,
                        "last_triggered": float(state.get("last_triggered", 0) or 0),
                        "last_reset": now_ts,
                    }
                    runtime_changed = True

        # Advanced alerts: RSI, MA crossover, score, signal, volume spike and cross events
        symbol_rules = adv_alerts.get(symbol, [])
        if not isinstance(symbol_rules, list):
            continue

        for rule in symbol_rules:
            if not isinstance(rule, dict):
                continue
            if _within_cooldown(rule, now_ts):
                continue

            rule_type = str(rule.get("type", "")).lower().strip()
            triggered = False
            message: str | None = None
            state_changed = False

            if rule_type == "rsi":
                triggered, message, state_changed = evaluate_rsi(symbol, result, rule, signal_state)

            elif rule_type == "ma":
                triggered, message, state_changed = evaluate_ma_crossover(symbol, result, rule, signal_state)

            elif rule_type == "cross":
                triggered, message, state_changed = evaluate_cross_event(symbol, result, rule, signal_state)

            elif rule_type == "score":
                triggered, message, state_changed = evaluate_score_above(symbol, result, rule, signal_state)

            elif rule_type == "signal":
                triggered, message, state_changed = evaluate_signal_state(symbol, result, rule, signal_state)

            elif rule_type == "volume_spike":
                try:
                    multiplier = float(rule.get("multiplier", 1.8) or 1.8)
                except (TypeError, ValueError):
                    multiplier = 1.8
                ratio = float(result.volume_ratio or 0)
                if result.is_volume_spike and ratio >= multiplier:
                    triggered = True
                    message = f"📦 *{symbol}* volume spike: {ratio:.2f}x (esik {multiplier:.2f}x)"

            if state_changed:
                signal_state_changed = True

            if triggered and message:
                logger.debug(
                    "alert triggered: user_id=%s symbol=%s type=%s message=%s",
                    user_id,
                    symbol,
                    rule_type,
                    message,
                )
                await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
                _mark_triggered(rule, now_ts)
                rule["fired"] = True
                adv_changed = True
            elif state_changed and not triggered:
                if rule.get("fired"):
                    rule["fired"] = False
                    rule["last_reset"] = now_ts
                    adv_changed = True

    if signal_state_changed:
        set_chat_signal_state(user_id, signal_state)
    if adv_changed:
        set_chat_advanced_alerts(user_id, adv_alerts)
    if runtime_changed:
        set_chat_alert_runtime_state(user_id, runtime_state)


async def alert_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled job entrypoint used by the bot job queue."""
    chat_id: int = context.job.chat_id
    user_id: int = int((context.job.data or {}).get("user_id", chat_id))
    await check_alerts(context, chat_id=chat_id, user_id=user_id)
