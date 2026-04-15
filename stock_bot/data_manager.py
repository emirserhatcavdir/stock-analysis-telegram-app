"""Thread-safe JSON persistence for portfolio, alerts, and RSI state."""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from stock_bot.config import PORTFOLIO_FILE, ALERTS_FILE, RSI_STATE_FILE, WATCHLIST_FILE, TRADES_FILE

logger = logging.getLogger(__name__)
_DATA_LOCK = threading.RLock()
ADV_ALERTS_FILE = ALERTS_FILE.with_name("advanced_alerts.json")
SIGNAL_STATE_FILE = ALERTS_FILE.with_name("signal_state.json")
USER_DATA_FILE = ALERTS_FILE.with_name("user_data.json")
ALERT_RUNTIME_STATE_FILE = ALERTS_FILE.with_name("alert_runtime_state.json")


# ── Generic JSON helpers ──────────────────────────────────────

def _copy_default(value: Any) -> Any:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return value


def _load_json_unlocked(path: Path, default: Any) -> Any:
    if not path.exists():
        _save_json_unlocked(path, default)
        return _copy_default(default)
    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            if attempt < attempts:
                time.sleep(0.05 * attempt)
                continue
            logger.exception("Cannot read %s – returning default", path)
            return _copy_default(default)
    return _copy_default(default)


def _save_json_unlocked(path: Path, data: Any) -> bool:
    tmp = path.with_suffix(path.suffix + ".tmp")
    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            tmp.replace(path)
            return True
        except OSError:
            if attempt < attempts:
                time.sleep(0.05 * attempt)
                continue
            logger.exception("Cannot write %s", path)
            return False
    return False


def load_json(path: Path, default: Any) -> Any:
    """Read JSON from *path*; create/return *default* when missing or corrupt."""
    with _DATA_LOCK:
        return _load_json_unlocked(path, default)


def save_json(path: Path, data: Any) -> bool:
    """Atomic write: write to .tmp then rename."""
    with _DATA_LOCK:
        return _save_json_unlocked(path, data)


def _normalize_user_id(user_id: int | str) -> str:
    return str(user_id).strip()


def _clean_portfolio(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, dict[str, Any]] = {}
    for symbol, entry in raw.items():
        if isinstance(entry, dict) and "shares" in entry and "buy_price" in entry:
            cleaned[str(symbol).strip().upper()] = dict(entry)
    return cleaned


def _clean_watchlist(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return sorted({str(item).strip().upper() for item in raw if str(item).strip()})


def _clean_alerts(raw: Any) -> dict[str, dict[str, float]]:
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, dict[str, float]] = {}
    for symbol, rules in raw.items():
        if not isinstance(rules, dict):
            continue
        valid: dict[str, float] = {}
        for side in ("above", "below"):
            if side in rules:
                try:
                    valid[side] = float(rules[side])
                except (TypeError, ValueError):
                    pass
        if valid:
            cleaned[str(symbol).strip().upper()] = valid
    return cleaned


def _clean_trades(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        side = str(row.get("side", "")).lower()
        if side not in ("buy", "sell"):
            continue
        symbol = str(row.get("symbol", "")).strip().upper()
        ts = str(row.get("timestamp", "")).strip()
        try:
            quantity = float(row.get("quantity", 0))
            price = float(row.get("price", 0))
            realized = float(row.get("realized_pnl", 0))
        except (TypeError, ValueError):
            continue
        if not symbol or not ts or quantity <= 0 or price <= 0:
            continue
        cleaned.append(
            {
                "timestamp": ts,
                "side": side,
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "realized_pnl": realized,
            }
        )
    return cleaned


def get_user_data(user_id: int | str) -> dict[str, Any]:
    key = _normalize_user_id(user_id)
    with _DATA_LOCK:
        raw_store = _load_json_unlocked(USER_DATA_FILE, {})
        store = raw_store if isinstance(raw_store, dict) else {}

        raw_user = store.get(key, {})
        raw_user = raw_user if isinstance(raw_user, dict) else {}

        portfolio = _clean_portfolio(raw_user.get("portfolio"))
        watchlist = _clean_watchlist(raw_user.get("watchlist"))
        alerts = _clean_alerts(raw_user.get("alerts"))
        trades = _clean_trades(raw_user.get("trades"))

        # Legacy fallback for first migration from global/chat-keyed files.
        if not portfolio:
            portfolio = _clean_portfolio(_load_json_unlocked(PORTFOLIO_FILE, {}))

        if not watchlist:
            legacy_watch = _load_json_unlocked(WATCHLIST_FILE, {})
            if isinstance(legacy_watch, dict):
                watchlist = _clean_watchlist(legacy_watch.get(key, []))

        if not alerts:
            legacy_alerts = _load_json_unlocked(ALERTS_FILE, {})
            if isinstance(legacy_alerts, dict):
                alerts = _clean_alerts(legacy_alerts.get(key, {}))

        if not trades:
            legacy_trades = _load_json_unlocked(TRADES_FILE, [])
            if isinstance(legacy_trades, dict):
                trades = _clean_trades(legacy_trades.get(key, []))
            else:
                trades = _clean_trades(legacy_trades)

        normalized = {
            "portfolio": portfolio,
            "watchlist": watchlist,
            "alerts": alerts,
            "trades": trades,
        }

        store[key] = normalized
        _save_json_unlocked(USER_DATA_FILE, store)
        return {
            "portfolio": dict(normalized["portfolio"]),
            "watchlist": list(normalized["watchlist"]),
            "alerts": {k: dict(v) for k, v in normalized["alerts"].items()},
            "trades": [dict(t) for t in normalized["trades"]],
        }


def save_user_data(user_id: int | str, data: dict[str, Any]) -> bool:
    key = _normalize_user_id(user_id)
    payload = data if isinstance(data, dict) else {}
    normalized = {
        "portfolio": _clean_portfolio(payload.get("portfolio", {})),
        "watchlist": _clean_watchlist(payload.get("watchlist", [])),
        "alerts": _clean_alerts(payload.get("alerts", {})),
        "trades": _clean_trades(payload.get("trades", [])),
    }
    with _DATA_LOCK:
        raw_store = _load_json_unlocked(USER_DATA_FILE, {})
        store = raw_store if isinstance(raw_store, dict) else {}
        store[key] = normalized
        return _save_json_unlocked(USER_DATA_FILE, store)


# ── Portfolio ─────────────────────────────────────────────────
# Structure: { "THYAO.IS": {"shares": 100, "buy_price": 280.5, "buy_date": "2026-01-15"}, … }

def load_portfolio(user_id: int | str = 0) -> dict[str, dict]:
    user_data = get_user_data(user_id)
    return _clean_portfolio(user_data.get("portfolio", {}))


def save_portfolio(user_id: int | str = 0, portfolio: dict[str, dict] | None = None) -> bool:
    portfolio = portfolio or {}
    user_data = get_user_data(user_id)
    user_data["portfolio"] = _clean_portfolio(portfolio)
    return save_user_data(user_id, user_data)


def upsert_portfolio_entry(user_id: int | str = 0, symbol: str = "", entry: dict[str, Any] | None = None) -> bool:
    if not symbol:
        return False
    entry = entry or {}
    user_data = get_user_data(user_id)
    portfolio = _clean_portfolio(user_data.get("portfolio", {}))
    portfolio[str(symbol).strip().upper()] = dict(entry)
    user_data["portfolio"] = portfolio
    return save_user_data(user_id, user_data)


def remove_portfolio_symbol(user_id: int | str = 0, symbol: str = "") -> tuple[bool, bool]:
    if not symbol:
        return True, False
    user_data = get_user_data(user_id)
    portfolio = _clean_portfolio(user_data.get("portfolio", {}))
    key = str(symbol).strip().upper()
    existed = key in portfolio
    if not existed:
        return True, False
    portfolio.pop(key, None)
    user_data["portfolio"] = portfolio
    return save_user_data(user_id, user_data), True


# ── Trades / Transactions ────────────────────────────────────
# Structure: [
#   {
#     "timestamp": "2026-03-28T10:35:00",
#     "side": "buy"|"sell",
#     "symbol": "THYAO.IS",
#     "quantity": 10,
#     "price": 280.5,
#     "realized_pnl": 120.0
#   },
#   ...
# ]

def load_trades(user_id: int | str = 0) -> list[dict[str, Any]]:
    user_data = get_user_data(user_id)
    return _clean_trades(user_data.get("trades", []))


def save_trades(user_id: int | str = 0, trades: list[dict[str, Any]] | None = None) -> bool:
    trades = trades or []
    user_data = get_user_data(user_id)
    user_data["trades"] = _clean_trades(trades)
    return save_user_data(user_id, user_data)


def apply_trade(
    user_id: int | str = 0,
    side: str = "",
    symbol: str = "",
    quantity: float = 0,
    price: float = 0,
    timestamp: str = "",
) -> tuple[bool, str, dict[str, Any] | None]:
    """Atomically apply buy/sell, update portfolio avg cost, and append trade history."""
    if side not in ("buy", "sell"):
        return False, "invalid side", None
    if quantity <= 0 or price <= 0:
        return False, "invalid quantity/price", None

    with _DATA_LOCK:
        user_data = get_user_data(user_id)
        portfolio = _clean_portfolio(user_data.get("portfolio", {}))
        entry = portfolio.get(symbol, {})
        if not isinstance(entry, dict):
            entry = {}

        old_shares = float(entry.get("shares", 0) or 0)
        old_avg = float(entry.get("buy_price", 0) or 0)
        old_realized = float(entry.get("realized_pnl", 0) or 0)

        realized_trade = 0.0
        if side == "buy":
            new_shares = old_shares + quantity
            new_avg = ((old_shares * old_avg) + (quantity * price)) / new_shares
            portfolio[symbol] = {
                "shares": round(new_shares, 8),
                "buy_price": round(new_avg, 4),
                "buy_date": timestamp.split("T", 1)[0],
                "realized_pnl": round(old_realized, 4),
            }
        else:
            if old_shares <= 0:
                return False, f"{symbol} için satılacak pozisyon yok.", None
            if quantity > old_shares:
                return False, f"Yetersiz adet. Mevcut: {old_shares}", None

            realized_trade = (price - old_avg) * quantity
            new_realized = old_realized + realized_trade
            new_shares = old_shares - quantity

            if new_shares > 0:
                portfolio[symbol] = {
                    "shares": round(new_shares, 8),
                    "buy_price": round(old_avg, 4),
                    "buy_date": entry.get("buy_date", timestamp.split("T", 1)[0]),
                    "realized_pnl": round(new_realized, 4),
                }
            else:
                portfolio.pop(symbol, None)

        trades = _clean_trades(user_data.get("trades", []))
        trade_row = {
            "timestamp": timestamp,
            "side": side,
            "symbol": symbol,
            "quantity": round(quantity, 8),
            "price": round(price, 4),
            "realized_pnl": round(realized_trade, 4),
        }
        trades.append(trade_row)

        user_data["portfolio"] = portfolio
        user_data["trades"] = trades

        if not save_user_data(user_id, user_data):
            return False, "kullanıcı verisi kaydedilemedi", None

        return True, "ok", trade_row


# ── Watchlist ────────────────────────────────────────────────
# Structure: { "<chat_id>": ["THYAO.IS", "ASELS.IS", ...], ... }

def load_watch_store() -> dict:
    raw = load_json(USER_DATA_FILE, {})
    store = raw if isinstance(raw, dict) else {}
    normalized: dict[str, list[str]] = {}
    for key, row in store.items():
        if not isinstance(row, dict):
            continue
        normalized[str(key)] = _clean_watchlist(row.get("watchlist", []))
    return normalized


def get_chat_watchlist(user_id: int | str = 0) -> list[str]:
    user_data = get_user_data(user_id)
    return _clean_watchlist(user_data.get("watchlist", []))


def set_chat_watchlist(user_id: int | str = 0, symbols: list[str] | None = None) -> bool:
    symbols = symbols or []
    user_data = get_user_data(user_id)
    user_data["watchlist"] = _clean_watchlist(symbols)
    return save_user_data(user_id, user_data)


def add_chat_watch_symbol(user_id: int | str = 0, symbol: str = "") -> tuple[bool, bool]:
    if not symbol:
        return False, False
    user_data = get_user_data(user_id)
    symbols = set(_clean_watchlist(user_data.get("watchlist", [])))
    normalized = str(symbol).strip().upper()
    if normalized in symbols:
        return True, False
    symbols.add(normalized)
    user_data["watchlist"] = sorted(symbols)
    return save_user_data(user_id, user_data), True


def remove_chat_watch_symbol(user_id: int | str = 0, symbol: str = "") -> tuple[bool, bool]:
    if not symbol:
        return True, False
    user_data = get_user_data(user_id)
    symbols = set(_clean_watchlist(user_data.get("watchlist", [])))
    normalized = str(symbol).strip().upper()
    if normalized not in symbols:
        return True, False
    symbols.remove(normalized)
    user_data["watchlist"] = sorted(symbols)
    return save_user_data(user_id, user_data), True


def add_to_watchlist(user_id: int | str, ticker: str) -> tuple[bool, bool]:
    normalized = str(ticker).strip().upper()
    if normalized and "." not in normalized:
        normalized = f"{normalized}.IS"
    return add_chat_watch_symbol(user_id, normalized)


def remove_from_watchlist(user_id: int | str, ticker: str) -> tuple[bool, bool]:
    normalized = str(ticker).strip().upper()
    if normalized and "." not in normalized:
        normalized = f"{normalized}.IS"
    return remove_chat_watch_symbol(user_id, normalized)


def get_watchlist(user_id: int | str) -> list[str]:
    return get_chat_watchlist(user_id)


# ── Legacy helper (currently unused) ─────────────────────────

def get_symbols(portfolio: dict[str, dict]) -> list[str]:
    return sorted(portfolio.keys())


# ── Alerts ────────────────────────────────────────────────────
# Structure: { "<chat_id>": { "SYM.IS": {"above": 300, "below": 250}, … } }

def load_alert_store() -> dict:
    raw = load_json(USER_DATA_FILE, {})
    store = raw if isinstance(raw, dict) else {}
    normalized: dict[str, dict[str, dict[str, float]]] = {}
    for key, row in store.items():
        if not isinstance(row, dict):
            continue
        normalized[str(key)] = _clean_alerts(row.get("alerts", {}))
    return normalized


def get_chat_alerts(user_id: int | str = 0) -> dict[str, dict[str, float]]:
    user_data = get_user_data(user_id)
    return _clean_alerts(user_data.get("alerts", {}))


def set_chat_alerts(user_id: int | str = 0, alerts: dict[str, dict[str, float]] | None = None) -> bool:
    alerts = alerts or {}
    user_data = get_user_data(user_id)
    user_data["alerts"] = _clean_alerts(alerts)
    return save_user_data(user_id, user_data)


def upsert_chat_alert(user_id: int | str = 0, symbol: str = "", side: str = "", target: float = 0.0) -> bool:
    if not symbol or side not in {"above", "below"}:
        return False
    user_data = get_user_data(user_id)
    alerts = _clean_alerts(user_data.get("alerts", {}))
    key = str(symbol).strip().upper()
    symbol_rules = alerts.get(key, {})
    symbol_rules = symbol_rules if isinstance(symbol_rules, dict) else {}
    symbol_rules[side] = float(target)
    alerts[key] = symbol_rules
    user_data["alerts"] = alerts
    return save_user_data(user_id, user_data)


def clear_chat_alert(user_id: int | str = 0, symbol: str = "", side: str | None = None) -> tuple[bool, bool]:
    if not symbol:
        return True, False
    user_data = get_user_data(user_id)
    alerts = _clean_alerts(user_data.get("alerts", {}))
    key = str(symbol).strip().upper()

    if key not in alerts:
        return True, False

    rules = alerts.get(key, {})
    if not isinstance(rules, dict):
        return True, False

    if side is None:
        alerts.pop(key, None)
    else:
        if side not in rules:
            return True, False
        rules.pop(side, None)
        if rules:
            alerts[key] = rules
        else:
            alerts.pop(key, None)

    user_data["alerts"] = alerts
    return save_user_data(user_id, user_data), True


def clear_chat_alert_if_matches(
    user_id: int | str,
    symbol: str,
    side: str,
    expected_target: float,
) -> tuple[bool, bool]:
    """Clear one side only if current threshold still matches expected_target."""
    user_data = get_user_data(user_id)
    alerts = _clean_alerts(user_data.get("alerts", {}))
    key = str(symbol).strip().upper()
    rules = alerts.get(key, {})
    if not isinstance(rules, dict) or side not in rules:
        return True, False

    try:
        current_target = float(rules[side])
    except (TypeError, ValueError):
        return True, False

    if current_target != float(expected_target):
        return True, False

    rules.pop(side, None)
    if rules:
        alerts[key] = rules
    else:
        alerts.pop(key, None)

    user_data["alerts"] = alerts
    return save_user_data(user_id, user_data), True


# ── Advanced alerts (multi-rule per symbol) ────────────────
# Structure: {
#   "<chat_id>": {
#     "SYM.IS": [
#       {"type": "rsi", "state": "oversold", "cooldown": 3600, "last_triggered": 0},
#       ...
#     ]
#   }
# }

def load_advanced_alert_store() -> dict:
    raw = load_json(ADV_ALERTS_FILE, {})
    return raw if isinstance(raw, dict) else {}


def get_chat_advanced_alerts(chat_id: int) -> dict[str, list[dict[str, Any]]]:
    store = load_advanced_alert_store()
    chat_data = store.get(str(chat_id), {})
    if not isinstance(chat_data, dict):
        return {}

    cleaned: dict[str, list[dict[str, Any]]] = {}
    for symbol, rules in chat_data.items():
        if not isinstance(rules, list):
            continue
        normalized_rules: list[dict[str, Any]] = []
        for r in rules:
            if not isinstance(r, dict):
                continue
            t = str(r.get("type", "")).strip().lower()
            if not t:
                continue
            item = dict(r)
            item["type"] = t
            item["cooldown"] = int(item.get("cooldown", 3600) or 3600)
            item["last_triggered"] = float(item.get("last_triggered", 0) or 0)
            item["fired"] = bool(item.get("fired", False))
            item["last_reset"] = float(item.get("last_reset", 0) or 0)
            normalized_rules.append(item)
        if normalized_rules:
            cleaned[str(symbol).strip().upper()] = normalized_rules
    return cleaned


def set_chat_advanced_alerts(chat_id: int, alerts: dict[str, list[dict[str, Any]]]) -> bool:
    store = load_advanced_alert_store()
    if alerts:
        store[str(chat_id)] = alerts
    else:
        store.pop(str(chat_id), None)
    return save_json(ADV_ALERTS_FILE, store)


def add_chat_advanced_alert(chat_id: int, symbol: str, rule: dict[str, Any]) -> tuple[bool, bool]:
    with _DATA_LOCK:
        raw = _load_json_unlocked(ADV_ALERTS_FILE, {})
        store = raw if isinstance(raw, dict) else {}
        key = str(chat_id)
        chat_data = store.get(key, {})
        chat_data = chat_data if isinstance(chat_data, dict) else {}

        symbol = symbol.strip().upper()
        rules = chat_data.get(symbol, [])
        rules = rules if isinstance(rules, list) else []

        fingerprint_keys = (
            "type",
            "condition",
            "side",
            "state",
            "direction",
            "threshold",
            "target",
            "signal",
            "multiplier",
        )
        incoming = {k: rule.get(k) for k in fingerprint_keys if k in rule}
        for existing in rules:
            if not isinstance(existing, dict):
                continue
            current = {k: existing.get(k) for k in fingerprint_keys if k in existing}
            if current == incoming:
                return True, False

        row = dict(rule)
        row["type"] = str(row.get("type", "")).lower()
        if "condition" in row and row["condition"] is not None:
            row["condition"] = str(row.get("condition", "")).lower()
        if "side" in row and row["side"] is not None:
            row["side"] = str(row.get("side", "")).lower()
        row["cooldown"] = int(row.get("cooldown", 3600) or 3600)
        row["last_triggered"] = float(row.get("last_triggered", 0) or 0)
        row["created_at"] = int(row.get("created_at", int(time.time())) or int(time.time()))
        row["fired"] = bool(row.get("fired", False))
        row["last_reset"] = float(row.get("last_reset", 0) or 0)
        if "summary" in row and row["summary"] is not None:
            row["summary"] = str(row.get("summary", "")).strip()
        rules.append(row)

        chat_data[symbol] = rules
        store[key] = chat_data
        return _save_json_unlocked(ADV_ALERTS_FILE, store), True


def clear_chat_advanced_alert(
    chat_id: int,
    symbol: str,
    rule_type: str | None = None,
    condition: str | None = None,
    side: str | None = None,
) -> tuple[bool, bool]:
    with _DATA_LOCK:
        raw = _load_json_unlocked(ADV_ALERTS_FILE, {})
        store = raw if isinstance(raw, dict) else {}
        key = str(chat_id)
        chat_data = store.get(key, {})
        if not isinstance(chat_data, dict):
            return True, False

        symbol = symbol.strip().upper()
        rules = chat_data.get(symbol)
        if not isinstance(rules, list):
            return True, False

        normalized_condition = str(condition).strip().lower() if condition is not None else None
        normalized_side = str(side).strip().lower() if side is not None else None

        if rule_type is None:
            removed = symbol in chat_data
            chat_data.pop(symbol, None)
        else:
            rt = rule_type.strip().lower()
            def _matches_rule(r: dict[str, Any]) -> bool:
                if str(r.get("type", "")).lower() != rt:
                    return False
                if normalized_condition is not None and str(r.get("condition", "")).lower() != normalized_condition:
                    return False
                if normalized_side is not None and str(r.get("side", "")).lower() != normalized_side:
                    return False
                return True

            new_rules = [r for r in rules if not (isinstance(r, dict) and _matches_rule(r))]
            removed = len(new_rules) != len(rules)
            if new_rules:
                chat_data[symbol] = new_rules
            else:
                chat_data.pop(symbol, None)

        if chat_data:
            store[key] = chat_data
        else:
            store.pop(key, None)

        return _save_json_unlocked(ADV_ALERTS_FILE, store), removed


# ── RSI state (for transition detection) ─────────────────────

def load_rsi_store() -> dict:
    raw = load_json(RSI_STATE_FILE, {})
    return raw if isinstance(raw, dict) else {}


def get_chat_rsi_state(chat_id: int) -> dict[str, str]:
    store = load_rsi_store()
    chat_data = store.get(str(chat_id), {})
    if isinstance(chat_data, dict):
        return {str(k): str(v) for k, v in chat_data.items()}
    return {}


def set_chat_rsi_state(chat_id: int, state: dict[str, str]) -> bool:
    store = load_rsi_store()
    if state:
        store[str(chat_id)] = state
    else:
        store.pop(str(chat_id), None)
    return save_json(RSI_STATE_FILE, store)


# ── Generic signal state (MACD/MA cross) ────────────────────

def load_signal_store() -> dict:
    raw = load_json(SIGNAL_STATE_FILE, {})
    return raw if isinstance(raw, dict) else {}


def get_chat_signal_state(chat_id: int) -> dict[str, str]:
    store = load_signal_store()
    chat_data = store.get(str(chat_id), {})
    if isinstance(chat_data, dict):
        return {str(k): str(v) for k, v in chat_data.items()}
    return {}


def set_chat_signal_state(chat_id: int, state: dict[str, str]) -> bool:
    store = load_signal_store()
    if state:
        store[str(chat_id)] = state
    else:
        store.pop(str(chat_id), None)
    return save_json(SIGNAL_STATE_FILE, store)


# ── Runtime alert state (anti-spam crossing memory) ─────────

def load_alert_runtime_store() -> dict:
    raw = load_json(ALERT_RUNTIME_STATE_FILE, {})
    return raw if isinstance(raw, dict) else {}


def get_chat_alert_runtime_state(chat_id: int) -> dict[str, dict[str, Any]]:
    store = load_alert_runtime_store()
    chat_data = store.get(str(chat_id), {})
    if not isinstance(chat_data, dict):
        return {}

    cleaned: dict[str, dict[str, Any]] = {}
    for key, value in chat_data.items():
        if not isinstance(value, dict):
            continue
        cleaned[str(key)] = {
            "fired": bool(value.get("fired", False)),
            "condition_met": bool(value.get("condition_met", False)),
            "last_triggered": float(value.get("last_triggered", 0) or 0),
            "last_reset": float(value.get("last_reset", 0) or 0),
        }
    return cleaned


def set_chat_alert_runtime_state(chat_id: int, state: dict[str, dict[str, Any]]) -> bool:
    store = load_alert_runtime_store()

    cleaned: dict[str, dict[str, Any]] = {}
    for key, value in (state or {}).items():
        if not isinstance(value, dict):
            continue
        cleaned[str(key)] = {
            "fired": bool(value.get("fired", False)),
            "condition_met": bool(value.get("condition_met", False)),
            "last_triggered": float(value.get("last_triggered", 0) or 0),
            "last_reset": float(value.get("last_reset", 0) or 0),
        }

    if cleaned:
        store[str(chat_id)] = cleaned
    else:
        store.pop(str(chat_id), None)
    return save_json(ALERT_RUNTIME_STATE_FILE, store)
