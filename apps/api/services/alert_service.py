"""Alert service shared by Telegram bot and FastAPI routes."""

from __future__ import annotations

import time
from typing import Any

from stock_bot.data_manager import (
    add_chat_advanced_alert,
    add_chat_watch_symbol,
    clear_chat_advanced_alert,
    clear_chat_alert,
    get_chat_advanced_alerts,
    get_chat_alerts,
    upsert_chat_alert,
)


def _clean_symbol(symbol: str) -> str:
    normalized = str(symbol or "").strip().upper()
    if normalized and "." not in normalized:
        normalized = f"{normalized}.IS"
    return normalized


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_num(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "0"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.{decimals}f}".rstrip("0").rstrip(".")


def _default_summary(rule: dict[str, Any]) -> str:
    t = str(rule.get("type") or "").lower().strip()
    side = str(rule.get("side") or "").lower().strip()
    condition = str(rule.get("condition") or "").lower().strip()
    target = _safe_float(rule.get("target"))
    threshold = _safe_float(rule.get("threshold"))

    if t == "rsi":
        if side == "above":
            return f"RSI above {_fmt_num(threshold if threshold is not None else 70, 0)}"
        if side == "below":
            return f"RSI below {_fmt_num(threshold if threshold is not None else 30, 0)}"
        return "RSI threshold alert"

    if t == "score":
        if side == "below":
            return f"Score below {_fmt_num(threshold if threshold is not None else 45, 0)}"
        return f"Score above {_fmt_num(threshold if threshold is not None else 80, 0)}"

    if t == "cross":
        if condition == "price_ma20":
            return "Price crossed below MA20" if side == "below" else "Price crossed above MA20"
        if condition == "price_ma50":
            return "Price crossed below MA50" if side == "below" else "Price crossed above MA50"
        if condition == "ma20_ma50":
            return "MA20 crossed below MA50" if side == "below" else "MA20 crossed above MA50"
        return "Cross event"

    if t == "price":
        if side == "below":
            return f"Price below {_fmt_num(target, 2)}"
        return f"Price above {_fmt_num(target, 2)}"

    if t == "signal":
        signal = str(rule.get("signal") or "").replace("_", " ").strip().title()
        return f"Signal becomes {signal or 'Target'}"

    if t == "ma":
        direction = str(rule.get("direction") or "").strip().lower() or "golden"
        return f"MA crossover ({direction})"

    if t == "volume_spike":
        mult = _safe_float(rule.get("multiplier")) or 1.8
        return f"Volume spike >= {mult:.2f}x"

    return str(rule.get("summary") or "Advanced alert")


def _normalize_advanced_rule(symbol: str, alert_type: str, rule: dict[str, Any]) -> dict[str, Any]:
    t = str(alert_type or rule.get("type") or "").strip().lower()
    side = str(rule.get("side") or "").strip().lower() or None

    normalized: dict[str, Any] = {
        "type": t,
        "created_at": int(rule.get("created_at", int(time.time())) or int(time.time())),
        "cooldown": int(rule.get("cooldown", 3600) or 3600),
        "last_triggered": float(rule.get("last_triggered", 0) or 0),
    }

    if t == "rsi":
        threshold = _safe_float(rule.get("threshold"))
        target = _safe_float(rule.get("target"))
        if threshold is None:
            threshold = target
        if side not in {"above", "below"}:
            state = str(rule.get("state") or "").strip().lower()
            if state in {"oversold", "below30"}:
                side = "below"
            elif state in {"overbought", "above70"}:
                side = "above"
        if side == "below":
            threshold = threshold if threshold is not None else 30.0
        else:
            side = "above"
            threshold = threshold if threshold is not None else 70.0
        normalized.update({
            "side": side,
            "threshold": threshold,
            "condition": "rsi_threshold",
        })

    elif t == "score":
        threshold = _safe_float(rule.get("threshold"))
        target = _safe_float(rule.get("target"))
        if threshold is None:
            threshold = target
        if side not in {"above", "below"}:
            side = "above"
        normalized.update({
            "side": side,
            "threshold": threshold if threshold is not None else (80.0 if side == "above" else 45.0),
            "condition": "score_threshold",
        })

    elif t in {"price_ma20_cross", "price_ma50_cross", "ma20_ma50_cross", "cross"}:
        condition = str(rule.get("condition") or "").strip().lower()
        if t != "cross":
            mapping = {
                "price_ma20_cross": "price_ma20",
                "price_ma50_cross": "price_ma50",
                "ma20_ma50_cross": "ma20_ma50",
            }
            condition = mapping[t]
        if condition not in {"price_ma20", "price_ma50", "ma20_ma50"}:
            condition = "price_ma20"
        if side not in {"above", "below"}:
            side = "above"
        normalized.update({
            "type": "cross",
            "condition": condition,
            "side": side,
        })

    else:
        passthrough = {
            "state": rule.get("state"),
            "direction": rule.get("direction"),
            "threshold": _safe_float(rule.get("threshold")),
            "signal": rule.get("signal"),
            "multiplier": _safe_float(rule.get("multiplier")),
        }
        for key, value in passthrough.items():
            if value is not None:
                normalized[key] = value

    normalized["symbol"] = _clean_symbol(symbol)
    normalized["alert_type"] = normalized.get("type", t)
    normalized["summary"] = str(rule.get("summary") or _default_summary(normalized))
    return normalized


def _to_alert_items(user_id: int, alerts: dict[str, Any], advanced_alerts: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for symbol, rules in (alerts or {}).items():
        if not isinstance(rules, dict):
            continue
        for side, target in rules.items():
            target_num = _safe_float(target)
            if target_num is None:
                continue
            row = {
                "user_id": user_id,
                "symbol": _clean_symbol(symbol),
                "type": "price",
                "alert_type": "price",
                "condition": str(side),
                "side": str(side),
                "target": target_num,
                "threshold": None,
                "created_at": None,
            }
            row["summary"] = _default_summary(row)
            items.append(row)

    for symbol, rules in (advanced_alerts or {}).items():
        if not isinstance(rules, list):
            continue
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            normalized = _normalize_advanced_rule(symbol, str(rule.get("type") or ""), rule)
            items.append(
                {
                    "user_id": user_id,
                    "symbol": normalized.get("symbol"),
                    "alert_type": normalized.get("alert_type"),
                    "condition": normalized.get("condition") or normalized.get("side") or normalized.get("direction") or normalized.get("state"),
                    "side": normalized.get("side"),
                    "target": _safe_float(normalized.get("target")),
                    "threshold": _safe_float(normalized.get("threshold")),
                    "created_at": int(normalized.get("created_at") or 0) or None,
                    "summary": str(normalized.get("summary") or _default_summary(normalized)),
                }
            )

    return items


def get_alerts(user_id: int) -> dict[str, Any]:
    alerts = get_chat_alerts(user_id)
    advanced_alerts = get_chat_advanced_alerts(user_id)
    return {
        "user_id": user_id,
        "alerts": alerts,
        "advanced_alerts": advanced_alerts,
        "alert_items": _to_alert_items(user_id, alerts, advanced_alerts),
    }


def add_price_alert(user_id: int, symbol: str, side: str, target: float) -> dict[str, Any]:
    saved = upsert_chat_alert(user_id, symbol, side, target)
    return {
        "ok": saved,
        "user_id": user_id,
        "symbol": symbol,
        "message": "Price alert added" if saved else "Price alert could not be saved",
    }


def add_advanced_alert(user_id: int, symbol: str, rule: dict[str, Any]) -> dict[str, Any]:
    symbol_norm = _clean_symbol(symbol)
    rule_norm = _normalize_advanced_rule(symbol_norm, str(rule.get("type") or ""), rule)
    saved, added = add_chat_advanced_alert(user_id, symbol_norm, rule_norm)
    return {
        "ok": saved and added,
        "user_id": user_id,
        "symbol": symbol_norm,
        "message": "Advanced alert added" if saved and added else "Advanced alert could not be saved",
    }


def remove_alert(user_id: int, symbol: str, alert_type: str | None = None, side: str | None = None) -> dict[str, Any]:
    normalized_symbol = _clean_symbol(symbol)
    alert_type_text = str(alert_type or "").strip().lower()
    if alert_type and alert_type_text != "price":
        condition = None
        mapped_type = alert_type_text
        cross_alias_map = {
            "price_ma20_cross": "price_ma20",
            "price_ma50_cross": "price_ma50",
            "ma20_ma50_cross": "ma20_ma50",
        }
        if alert_type_text in cross_alias_map:
            mapped_type = "cross"
            condition = cross_alias_map[alert_type_text]
        saved, removed = clear_chat_advanced_alert(user_id, normalized_symbol, mapped_type, condition=condition, side=side)
    else:
        saved, removed = clear_chat_alert(user_id, normalized_symbol, side)
    return {
        "ok": saved and removed,
        "user_id": user_id,
        "symbol": normalized_symbol,
        "message": "Alert removed" if saved and removed else "Alert could not be removed",
    }
