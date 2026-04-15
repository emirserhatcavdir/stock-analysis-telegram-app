"""All Telegram command handlers."""

from __future__ import annotations

import io
import logging
import time
from datetime import datetime
from datetime import date
from functools import wraps

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import ContextTypes

from stock_bot.analysis import AnalysisResult, analyze, fmt, get_current_price, normalize_symbol
from stock_bot.alerts import alert_job
from stock_bot.charts import generate_chart
from stock_bot.config import ALERT_INTERVAL_SECONDS, MA_LONG, MA_MID, MA_SHORT, MINI_APP_URL, RSI_PERIOD
from stock_bot.data_manager import (
    add_to_watchlist,
    add_chat_watch_symbol,
    apply_trade,
    add_chat_advanced_alert,
    clear_chat_advanced_alert,
    clear_chat_alert,
    get_watchlist,
    get_chat_advanced_alerts,
    get_chat_alerts,
    get_chat_watchlist,
    load_trades,
    load_portfolio,
    remove_from_watchlist,
    remove_chat_watch_symbol,
    remove_portfolio_symbol,
    upsert_chat_alert,
    upsert_portfolio_entry,
)
from stock_bot.scanner import SCAN_UNIVERSES, run_scan
from stock_bot.portfolio_analytics import (
    compute_portfolio_analytics,
    get_allocation,
    get_best_position,
    get_losers,
    get_worst_position,
    get_winners,
)
from stock_bot.scoring import rank_symbols, scan_top_stocks, score_symbol
from stock_bot.reports import daily_report_job
from stock_bot.market_overview import build_market_overview
from stock_bot.fundamentals import get_fundamentals
from stock_bot.commentary import build_group_commentary, build_symbol_commentary

logger = logging.getLogger(__name__)


def _get_user_id(update: Update) -> int:
    if update.effective_user and update.effective_user.id is not None:
        return int(update.effective_user.id)
    if update.effective_chat and update.effective_chat.id is not None:
        return int(update.effective_chat.id)
    return 0


def _dashboard_webapp_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📊 Dashboard", web_app=WebAppInfo(url=MINI_APP_URL))]]
    )


# ── Decorator ─────────────────────────────────────────────────

def guard(handler):
    """Catch-all wrapper so a single command failure doesn't crash the bot."""
    @wraps(handler)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            await handler(update, context)
        except Exception:
            logger.exception("Command failed: %s", handler.__name__)
            if update.effective_message:
                await update.effective_message.reply_text(
                    "⚠️ Beklenmedik hata. Tekrar dene."
                )
    return wrapped


# ── /start ────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("📊 Dashboard", web_app=WebAppInfo(url=MINI_APP_URL))]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Selam 👋\n\n"
        "Kendi geliştirdiğim hisse analiz botunu beta olarak açtım 📈\n\n"
        "İçinde:\n"
        "- RSI ve hareketli ortalama analizleri\n"
        "- Al/Sat sinyalleri\n"
        "- Scan ile hisse tarama\n"
        "- Portföy takibi\n"
        "- Gelişmiş grafikler\n\n"
        "Şimdiden teşekkürler 🙏",
        reply_markup=reply_markup,
    )

@guard
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


# ── /add (portfolio position) ─────────────────────────────────

@guard
async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /add THYAO")
        return

    symbol = normalize_symbol(context.args[0])
    user_id = _get_user_id(update)
    saved, added = add_to_watchlist(user_id, symbol)
    if not added:
        await update.message.reply_text(f"ℹ️ {symbol} zaten izleme listesinde.")
        return

    if saved:
        await update.message.reply_text(f"✅ *{symbol}* izleme listesine eklendi.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Kaydedilemedi.")


# ── /remove ───────────────────────────────────────────────────

@guard
async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /remove THYAO")
        return
    user_id = _get_user_id(update)
    symbol = normalize_symbol(context.args[0])
    saved, removed = remove_from_watchlist(user_id, symbol)
    if not removed:
        await update.message.reply_text(f"ℹ️ {symbol} izleme listesinde yok.")
        return
    if saved:
        await update.message.reply_text(f"✅ {symbol} izleme listesinden silindi.")
    else:
        await update.message.reply_text("❌ Güncellenemedi.")


# ── /buy, /sell, /trades ────────────────────────────────────

def _parse_trade_args(args: list[str]) -> tuple[str | None, float | None, float | None, str | None]:
    if len(args) < 3:
        return None, None, None, "Kullanım: /buy THYAO 10 280.50"
    symbol = normalize_symbol(args[0])
    try:
        quantity = float(args[1])
        price = float(args[2])
    except ValueError:
        return None, None, None, "❌ Adet ve fiyat sayı olmalı."
    if quantity <= 0:
        return None, None, None, "❌ Adet sıfırdan büyük olmalı."
    if price <= 0:
        return None, None, None, "❌ Fiyat sıfırdan büyük olmalı."
    return symbol, quantity, price, None


@guard
async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol, quantity, price, err = _parse_trade_args(context.args or [])
    if err:
        await update.message.reply_text(err)
        return

    probe = get_current_price(symbol)
    if probe is None:
        await update.message.reply_text(f"❌ {symbol} için veri alınamadı.")
        return

    user_id = _get_user_id(update)
    ok, message, trade = apply_trade(
        user_id=user_id,
        side="buy",
        symbol=symbol,
        quantity=quantity,
        price=price,
        timestamp=datetime.now().isoformat(timespec="seconds"),
    )
    if not ok or trade is None:
        await update.message.reply_text(f"❌ İşlem başarısız: {message}")
        return

    portfolio = load_portfolio(user_id)
    entry = portfolio.get(symbol, {})
    avg_cost = float(entry.get("buy_price", 0) or 0)
    total_shares = float(entry.get("shares", 0) or 0)

    await update.message.reply_text(
        f"✅ ALIŞ kaydedildi: {symbol}\n"
        f"Adet: {quantity} | Fiyat: {price:.2f} TL\n"
        f"Yeni Ortalama Maliyet: {avg_cost:.2f} TL\n"
        f"Toplam Adet: {total_shares}",
    )


@guard
async def cmd_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol, quantity, price, err = _parse_trade_args(context.args or [])
    if err:
        await update.message.reply_text(err.replace("/buy", "/sell"))
        return

    user_id = _get_user_id(update)
    ok, message, trade = apply_trade(
        user_id=user_id,
        side="sell",
        symbol=symbol,
        quantity=quantity,
        price=price,
        timestamp=datetime.now().isoformat(timespec="seconds"),
    )
    if not ok or trade is None:
        await update.message.reply_text(f"❌ İşlem başarısız: {message}")
        return

    realized = float(trade.get("realized_pnl", 0) or 0)
    portfolio = load_portfolio(user_id)
    entry = portfolio.get(symbol)
    if entry:
        remain = float(entry.get("shares", 0) or 0)
        avg_cost = float(entry.get("buy_price", 0) or 0)
        remain_msg = f"Kalan Adet: {remain} | Ortalama Maliyet: {avg_cost:.2f} TL"
    else:
        remain_msg = "Pozisyon kapandı."

    await update.message.reply_text(
        f"✅ SATIŞ kaydedildi: {symbol}\n"
        f"Adet: {quantity} | Fiyat: {price:.2f} TL\n"
        f"Gerçekleşen K/Z: {realized:+.2f} TL\n"
        f"{remain_msg}",
    )


@guard
async def cmd_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    trades = load_trades(user_id)
    if not trades:
        await update.message.reply_text("İşlem geçmişi boş.")
        return

    total_realized = sum(float(t.get("realized_pnl", 0) or 0) for t in trades)
    recent = trades[-10:]
    lines = [
        "🧾 *Son İşlemler*",
        f"Toplam Gerçekleşen K/Z: {total_realized:+.2f} TL",
        "",
    ]

    for t in reversed(recent):
        ts = str(t.get("timestamp", ""))
        side = str(t.get("side", "")).upper()
        symbol = str(t.get("symbol", ""))
        qty = float(t.get("quantity", 0) or 0)
        price = float(t.get("price", 0) or 0)
        realized = float(t.get("realized_pnl", 0) or 0)
        lines.append(
            f"• {ts} | {side} {symbol} {qty} @ {price:.2f} TL | K/Z: {realized:+.2f}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /portfolio ────────────────────────────────────────────────

@guard
async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    portfolio = load_portfolio(user_id)
    if not portfolio:
        await update.message.reply_text("Portföy boş. /buy ile pozisyon aç.")
        return

    lines = [
        "💼 *Portföy*",
    ]

    for symbol in sorted(portfolio.keys()):
        entry = portfolio.get(symbol, {})
        shares = float(entry.get("shares", 0) or 0)
        avg_cost = float(entry.get("buy_price", 0) or 0)
        lines.append(
            f"• {symbol}: {shares:g} adet | Ortalama maliyet {avg_cost:.2f} TL"
        )

    text = "\n".join(lines)
    try:
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception:
        # Fallback: strip markdown if it fails
        await update.message.reply_text(text.replace("*", "").replace("_", ""))


# ── /summary, /performance, /allocation, /winners, /losers ──

@guard
async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    portfolio = load_portfolio(user_id)
    if not portfolio:
        await update.message.reply_text("Portföy boş. /add veya /buy ile pozisyon aç.")
        return

    await update.message.reply_text("⏳ Portföy özeti hazırlanıyor...")
    analytics = compute_portfolio_analytics(portfolio, load_trades(user_id))
    if not analytics.positions:
        await update.message.reply_text("❌ Özet için yeterli veri yok.")
        return

    best = max(analytics.positions, key=lambda p: p.unrealized_pct)
    worst = min(analytics.positions, key=lambda p: p.unrealized_pct)

    lines = [
        "📌 *Portföy Özeti*",
        f"Pozisyon Sayısı: {len(analytics.positions)}",
        f"Toplam Değer: {analytics.total_value:,.2f} TL",
        f"Toplam Maliyet: {analytics.total_cost:,.2f} TL",
        f"Gerçekleşmemiş K/Z: {analytics.unrealized_pnl:+,.2f} TL",
        f"Gerçekleşmiş K/Z: {analytics.realized_pnl:+,.2f} TL",
        f"Net K/Z: {analytics.net_pnl:+,.2f} TL",
        "",
        f"🏆 En İyi: {best.symbol} ({best.unrealized_pct:+.2f}%)",
        f"📉 En Zayıf: {worst.symbol} ({worst.unrealized_pct:+.2f}%)",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@guard
async def cmd_performance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    portfolio = load_portfolio(user_id)
    if not portfolio:
        await update.message.reply_text("Portföy boş. /add veya /buy ile pozisyon aç.")
        return

    await update.message.reply_text("⏳ Performans hesaplanıyor...")
    analytics = compute_portfolio_analytics(portfolio, load_trades(user_id))
    if not analytics.positions:
        await update.message.reply_text("❌ Performans için yeterli veri yok.")
        return

    if analytics.daily_abs is None or analytics.daily_pct is None:
        daily_line = "Günlük: veri yetersiz"
    else:
        daily_line = f"Günlük: {analytics.daily_abs:+,.2f} TL ({analytics.daily_pct:+.2f}%)"

    if analytics.weekly_abs is None or analytics.weekly_pct is None:
        weekly_line = "Haftalık: veri yetersiz"
    else:
        weekly_line = f"Haftalık: {analytics.weekly_abs:+,.2f} TL ({analytics.weekly_pct:+.2f}%)"

    lines = [
        "📊 *Performans*",
        daily_line,
        weekly_line,
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@guard
async def cmd_allocation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    portfolio = load_portfolio(user_id)
    if not portfolio:
        await update.message.reply_text("Portföy boş. /add veya /buy ile pozisyon aç.")
        return

    analytics = compute_portfolio_analytics(portfolio, load_trades(user_id))
    rows = get_allocation(analytics)
    if not rows:
        await update.message.reply_text("❌ Dağılım için yeterli veri yok.")
        return

    lines = ["🧩 *Portföy Dağılımı*"]
    for pos, pct in rows:
        lines.append(f"• {pos.symbol}: %{pct:.2f} ({pos.value:,.2f} TL)")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@guard
async def cmd_winners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    portfolio = load_portfolio(user_id)
    if not portfolio:
        await update.message.reply_text("Portföy boş. /add veya /buy ile pozisyon aç.")
        return

    analytics = compute_portfolio_analytics(portfolio, load_trades(user_id))
    rows = get_winners(analytics, limit=5)
    if not rows:
        await update.message.reply_text("Kazanan pozisyon bulunamadı.")
        return

    lines = ["🏆 *En İyi Performanslı Hisseler*"]
    for pos in rows:
        lines.append(
            f"• {pos.symbol}: {pos.unrealized_pct:+.2f}% | K/Z {pos.unrealized_pnl:+,.2f} TL"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@guard
async def cmd_losers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    portfolio = load_portfolio(user_id)
    if not portfolio:
        await update.message.reply_text("Portföy boş. /add veya /buy ile pozisyon aç.")
        return

    analytics = compute_portfolio_analytics(portfolio, load_trades(user_id))
    rows = get_losers(analytics, limit=5)
    if not rows:
        await update.message.reply_text("Kaybeden pozisyon bulunamadı.")
        return

    lines = ["📉 *En Zayıf Performanslı Hisseler*"]
    for pos in rows:
        lines.append(
            f"• {pos.symbol}: {pos.unrealized_pct:+.2f}% | K/Z {pos.unrealized_pnl:+,.2f} TL"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /price ────────────────────────────────────────────────────

@guard
async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /price THYAO")
        return
    symbol = normalize_symbol(context.args[0])
    price = get_current_price(symbol)
    if price is None:
        await update.message.reply_text(f"❌ {symbol} için veri bulunamadı.")
    else:
        await update.message.reply_text(f"💰 *{symbol}*: {price:.2f} TL", parse_mode="Markdown")


# ── /analyze ──────────────────────────────────────────────────

@guard
async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /analyze THYAO")
        return
    symbol = normalize_symbol(context.args[0])
    await update.message.reply_text("⏳ Analiz yapılıyor...")
    result = analyze(symbol)
    if result is None:
        await update.message.reply_text(f"❌ {symbol} için veri alınamadı.")
        return
    try:
        await update.message.reply_text(result.format_professional_report(), parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(result.format_professional_report().replace("*", ""))


# ── /chart ────────────────────────────────────────────────────

@guard
async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /chart THYAO [3mo|6mo|1y|2y]")
        return
    symbol = normalize_symbol(context.args[0])
    period = context.args[1] if len(context.args) > 1 else "6mo"
    allowed = {"1mo", "3mo", "6mo", "1y", "2y", "5y"}
    if period not in allowed:
        await update.message.reply_text(f"Geçersiz periyot. Seçenekler: {', '.join(sorted(allowed))}")
        return

    await update.message.reply_text("⏳ Grafik hazırlanıyor...")
    png = generate_chart(symbol, period=period)
    if png is None:
        await update.message.reply_text(f"❌ {symbol} için grafik oluşturulamadı.")
        return
    await update.message.reply_photo(
        photo=io.BytesIO(png),
        caption=f"📊 {symbol} — {period}",
    )


# ── /score & /rank ──────────────────────────────────────────

@guard
async def cmd_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /score THYAO")
        return

    symbol = normalize_symbol(context.args[0])
    await update.message.reply_text(f"⏳ Skor hesaplanıyor: {symbol}")
    scored = score_symbol(symbol)
    if scored is None:
        await update.message.reply_text(f"❌ {symbol} için skor üretilemedi.")
        return

    try:
        await update.message.reply_text(scored.format_text(), parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(scored.format_text().replace("*", ""))


@guard
async def cmd_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    target = context.args[0].strip().lower() if context.args else "bist30"

    if target == "bist30":
        symbols = SCAN_UNIVERSES.get("bist30", [])
        if not symbols:
            await update.message.reply_text("❌ BIST listesi bulunamadı.")
            return

        await update.message.reply_text("⏳ BIST taraması yapılıyor (top 10)...")
        ranked = scan_top_stocks(symbols, top_n=10, max_symbols=30)
        if not ranked:
            await update.message.reply_text("❌ Tarama sonucu bulunamadı.")
            return

        lines = ["*BIST Top 10 (Score)*"]
        for idx, row in enumerate(ranked, start=1):
            lines.append(f"{idx}. {row.symbol.replace('.IS', '')} - Score: {row.score} ({row.signal})")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    if target == "portfolio":
        symbols = sorted(load_portfolio(user_id).keys())
        title = "📊 *Portföy Skor Sıralaması*"
    elif target == "watchlist":
        symbols = get_chat_watchlist(user_id)
        title = "👀 *Watchlist Skor Sıralaması*"
    else:
        await update.message.reply_text("Kullanım: /rank portfolio|watchlist")
        return

    if not symbols:
        await update.message.reply_text("Sıralanacak hisse bulunamadı.")
        return

    await update.message.reply_text("⏳ Sıralama hesaplanıyor...")
    ranked = rank_symbols(symbols)
    if not ranked:
        await update.message.reply_text("❌ Sıralama üretilemedi.")
        return

    lines = [title]
    for idx, row in enumerate(ranked[:10], start=1):
        lines.append(f"{idx}. {row.symbol} — {row.score}/100 ({row.strength})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /scan ───────────────────────────────────────────────────

@guard
async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = context.args[0].strip().lower() if context.args else "bist30"
    user_id = _get_user_id(update)

    if target == "bist30":
        symbols = SCAN_UNIVERSES.get("bist30", [])
        if not symbols:
            await update.message.reply_text("❌ BIST listesi bulunamadı.")
            return

        await update.message.reply_text("⏳ Scan: BIST ticker listesi analiz ediliyor...")
        ranked = scan_top_stocks(symbols, top_n=10, max_symbols=30)
        if not ranked:
            await update.message.reply_text("❌ Tarama sonucu bulunamadı.")
            return

        lines = ["*Scan Result (Top 10)*"]
        for idx, row in enumerate(ranked, start=1):
            lines.append(f"{idx}. {row.symbol.replace('.IS', '')} - Score: {row.score} ({row.signal})")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    if target not in {"portfolio", "watchlist"}:
        await update.message.reply_text("Kullanım: /scan [bist30|portfolio|watchlist]")
        return

    portfolio_symbols = sorted(load_portfolio(user_id).keys()) if target == "portfolio" else None
    watchlist_symbols = get_chat_watchlist(user_id) if target == "watchlist" else None

    if target == "portfolio" and not portfolio_symbols:
        await update.message.reply_text("Portföy boş. /add veya /buy ile hisse ekle.")
        return
    if target == "watchlist" and not watchlist_symbols:
        await update.message.reply_text("Watchlist boş. /watch ile hisse ekle.")
        return

    await update.message.reply_text(f"⏳ Tarama başlatıldı: {target.upper()}")
    report = run_scan(target, portfolio_symbols=portfolio_symbols, watchlist_symbols=watchlist_symbols)
    if report is None:
        await update.message.reply_text("❌ Tarama yapılamadı.")
        return

    try:
        await update.message.reply_text(report.format_text(), parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(report.format_text().replace("*", ""))


# ── /market, /bist, /movers, /volumeleaders ───────────────

@guard
async def cmd_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Piyasa özeti hazırlanıyor...")
    report = build_market_overview("bist30", top_n=5)
    if report is None or report.analyzed_count == 0:
        await update.message.reply_text("❌ Piyasa özeti üretilemedi.")
        return

    try:
        await update.message.reply_text(report.format_market_text(), parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(report.format_market_text().replace("*", ""))


@guard
async def cmd_bist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ BIST özeti hazırlanıyor...")
    report = build_market_overview("bist30", top_n=3)
    if report is None or report.analyzed_count == 0:
        await update.message.reply_text("❌ BIST özeti üretilemedi.")
        return

    lines = [
        "*BIST30 Hızlı Özet*",
        f"Analiz edilen: {report.analyzed_count} | Hata: {report.failed_count}",
    ]
    if report.avg_change_pct is not None:
        lines.append(f"Ortalama günlük değişim: {report.avg_change_pct:+.2f}%")
    lines.append(
        f"Trend: Yükseliş {report.uptrend_count} | Düşüş {report.downtrend_count} | Yatay {report.sideways_count}"
    )

    if report.gainers:
        best = report.gainers[0]
        lines.append(f"En güçlü: {best.symbol} ({best.change_pct:+.2f}%)")
    if report.losers:
        weak = report.losers[0]
        lines.append(f"En zayıf: {weak.symbol} ({weak.change_pct:+.2f}%)")

    try:
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("\n".join(lines).replace("*", ""))


@guard
async def cmd_movers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Mover listesi hazırlanıyor...")
    report = build_market_overview("bist30", top_n=5)
    if report is None or report.analyzed_count == 0:
        await update.message.reply_text("❌ Mover listesi üretilemedi.")
        return

    try:
        await update.message.reply_text(report.format_movers_text(), parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(report.format_movers_text().replace("*", ""))


@guard
async def cmd_volumeleaders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Hacim liderleri hazırlanıyor...")
    report = build_market_overview("bist30", top_n=8)
    if report is None or report.analyzed_count == 0:
        await update.message.reply_text("❌ Hacim liderleri üretilemedi.")
        return

    try:
        await update.message.reply_text(report.format_volume_leaders_text(), parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(report.format_volume_leaders_text().replace("*", ""))


# ── /fundamental, /fundamentals ───────────────────────────

@guard
async def cmd_fundamental(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /fundamental THYAO")
        return

    symbol = normalize_symbol(context.args[0])
    await update.message.reply_text(f"⏳ Temel analiz hazırlanıyor: {symbol}")
    snapshot = get_fundamentals(symbol)
    if snapshot is None:
        await update.message.reply_text(f"❌ {symbol} için fundamental veri alınamadı.")
        return

    try:
        await update.message.reply_text(snapshot.format_text(), parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(snapshot.format_text().replace("*", ""))


@guard
async def cmd_fundamentals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /fundamentals portfolio|watchlist")
        return

    target = context.args[0].strip().lower()
    user_id = _get_user_id(update)
    if target == "portfolio":
        symbols = sorted(load_portfolio(user_id).keys())
        title = "📚 *Portföy Fundamental Özeti*"
    elif target == "watchlist":
        symbols = get_chat_watchlist(user_id)
        title = "📚 *Watchlist Fundamental Özeti*"
    else:
        await update.message.reply_text("Kullanım: /fundamentals portfolio|watchlist")
        return

    if not symbols:
        await update.message.reply_text("Listede hisse bulunamadı.")
        return

    await update.message.reply_text("⏳ Fundamental özet hazırlanıyor...")
    rows: list[str] = []
    failed = 0
    for symbol in symbols[:12]:
        snapshot = get_fundamentals(symbol)
        if snapshot is None:
            failed += 1
            continue
        rows.append(snapshot.format_compact_row())

    if not rows:
        await update.message.reply_text("❌ Fundamental özet üretilemedi.")
        return

    lines = [title, f"Analiz edilen: {len(rows)} | Hata: {failed}", ""]
    lines.extend(rows)
    try:
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("\n".join(lines).replace("*", ""))


# ── /comment, /commentary ──────────────────────────────────

@guard
async def cmd_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /comment THYAO")
        return

    symbol = normalize_symbol(context.args[0])
    await update.message.reply_text(f"⏳ Yorum hazırlanıyor: {symbol}")
    result = build_symbol_commentary(symbol)
    if result is None:
        await update.message.reply_text(f"❌ {symbol} için yorum üretilemedi.")
        return

    try:
        await update.message.reply_text(result.format_text(), parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(result.format_text().replace("*", ""))


@guard
async def cmd_commentary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /commentary portfolio|watchlist")
        return

    target = context.args[0].strip().lower()
    user_id = _get_user_id(update)
    if target == "portfolio":
        symbols = sorted(load_portfolio(user_id).keys())
        label = "Portfoy"
    elif target == "watchlist":
        symbols = get_chat_watchlist(user_id)
        label = "Watchlist"
    else:
        await update.message.reply_text("Kullanım: /commentary portfolio|watchlist")
        return

    if not symbols:
        await update.message.reply_text("Listede hisse bulunamadı.")
        return

    await update.message.reply_text("⏳ Grup yorumu hazırlanıyor...")
    result = build_group_commentary(symbols[:15], label)
    if result is None:
        await update.message.reply_text("❌ Grup yorumu üretilemedi.")
        return

    try:
        await update.message.reply_text(result.format_text(), parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(result.format_text().replace("*", ""))


# ── /watch, /unwatch, /watchlist ───────────────────────────

@guard
async def cmd_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /watch THYAO")
        return

    symbol = normalize_symbol(context.args[0])
    user_id = _get_user_id(update)
    saved, added = add_to_watchlist(user_id, symbol)
    if not added:
        await update.message.reply_text(f"ℹ️ {symbol} zaten izleme listesinde.")
        return

    if saved:
        await update.message.reply_text(f"✅ *{symbol}* izleme listesine eklendi.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Kaydedilemedi.")


@guard
async def cmd_unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /unwatch THYAO")
        return

    symbol = normalize_symbol(context.args[0])
    user_id = _get_user_id(update)
    saved, removed = remove_from_watchlist(user_id, symbol)
    if not removed:
        await update.message.reply_text(f"ℹ️ {symbol} izleme listesinde yok.")
        return

    if saved:
        await update.message.reply_text(f"✅ {symbol} izleme listesinden silindi.")
    else:
        await update.message.reply_text("❌ Kaydedilemedi.")


@guard
async def cmd_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    watchlist = get_watchlist(user_id)
    if not watchlist:
        await update.message.reply_text("İzleme listen boş. /watch THYAO ile ekleyebilirsin.")
        return

    lines = ["👀 *İzleme Listesi:*"]
    for symbol in watchlist:
        price = get_current_price(symbol)
        if price is None:
            lines.append(f"• {symbol}: veri alınamadı")
        else:
            lines.append(f"• {symbol}: {price:.2f} TL")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@guard
async def cmd_watchlist_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /watchlist_add THYAO")
        return

    symbol = normalize_symbol(context.args[0])
    user_id = _get_user_id(update)
    saved, added = add_to_watchlist(user_id, symbol)
    if not added:
        await update.message.reply_text(f"ℹ️ {symbol} zaten izleme listesinde.")
        return

    if saved:
        await update.message.reply_text(f"✅ *{symbol}* izleme listesine eklendi.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Kaydedilemedi.")


@guard
async def cmd_watchlist_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /watchlist_remove THYAO")
        return

    symbol = normalize_symbol(context.args[0])
    user_id = _get_user_id(update)
    saved, removed = remove_from_watchlist(user_id, symbol)
    if not removed:
        await update.message.reply_text(f"ℹ️ {symbol} izleme listesinde yok.")
        return

    if saved:
        await update.message.reply_text(f"✅ {symbol} izleme listesinden silindi.")
    else:
        await update.message.reply_text("❌ Kaydedilemedi.")


# ── /alert ────────────────────────────────────────────────────

DIRECTION_MAP = {
    "above": "above", "ust": "above", "ustte": "above", "üst": "above",
    "below": "below", "alt": "below", "altta": "below",
}

ADV_TYPES = {"rsi", "macd", "ma", "change", "volume_spike", "score", "signal"}


@guard
async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args or []) < 2:
        await update.message.reply_text(
            "Kullanım:\n"
            "/alert THYAO above 300\n"
            "/alert THYAO score above 80\n"
            "/alert THYAO signal strong_buy\n"
            "/alert THYAO rsi oversold|overbought\n"
            "/alert THYAO macd bullish|bearish\n"
            "/alert THYAO ma golden|death\n"
            "/alert THYAO change 3\n"
            "/alert THYAO volume_spike [1.8]"
        )
        return
    symbol = normalize_symbol(context.args[0])
    user_id = _get_user_id(update)
    mode = context.args[1].lower().strip()

    # Backward-compatible price alerts
    side = DIRECTION_MAP.get(mode)
    if side is not None:
        if len(context.args) < 3:
            await update.message.reply_text("Kullanım: /alert THYAO above|below 300")
            return
        try:
            target = float(context.args[2])
        except ValueError:
            await update.message.reply_text("Fiyat sayı olmalı.")
            return
        if target <= 0:
            await update.message.reply_text("Fiyat sıfırdan büyük olmalı.")
            return

        direction_text = "üstüne çıkarsa" if side == "above" else "altına düşerse"
        if upsert_chat_alert(user_id, symbol, side, target):
            await update.message.reply_text(
                f"🔔 Alarm: {symbol} {target:.2f} TL {direction_text} bildirim gelecek."
            )
        else:
            await update.message.reply_text("❌ Kaydedilemedi.")
        return

    if mode not in ADV_TYPES:
        await update.message.reply_text("Alarm tipi: above/below/rsi/macd/ma/change/volume_spike")
        return

    rule: dict[str, object] = {
        "type": mode,
        "cooldown": 3600,
        "last_triggered": 0.0,
        "created_at": int(time.time()),
    }

    if mode == "score":
        if len(context.args) < 3:
            await update.message.reply_text("Kullanım: /alert THYAO score above 80")
            return

        threshold_arg_index = 2
        if context.args[2].lower().strip() == "above":
            if len(context.args) < 4:
                await update.message.reply_text("Kullanım: /alert THYAO score above 80")
                return
            threshold_arg_index = 3

        try:
            threshold = float(context.args[threshold_arg_index])
        except ValueError:
            await update.message.reply_text("Skor eşiği sayı olmalı. Örn: /alert THYAO score above 80")
            return

        if threshold < 0 or threshold > 100:
            await update.message.reply_text("Skor eşiği 0-100 arasında olmalı.")
            return

        rule["threshold"] = threshold
        desc = f"Score >= {threshold:.0f}"

    elif mode == "signal":
        if len(context.args) < 3:
            await update.message.reply_text("Kullanım: /alert THYAO signal strong_buy")
            return
        signal = context.args[2].lower().strip().replace(" ", "_")
        if signal in {"strongbuy", "strong_buy"}:
            signal = "strong_buy"
        if signal not in {"strong_buy", "buy", "neutral", "sell"}:
            await update.message.reply_text("Signal: strong_buy | buy | neutral | sell")
            return
        rule["signal"] = signal
        desc = f"Signal {signal.replace('_', ' ').title()}"

    elif mode == "rsi":
        if len(context.args) < 3:
            await update.message.reply_text("Kullanım: /alert THYAO rsi oversold|overbought")
            return
        state = context.args[2].lower().strip()
        if state not in {"oversold", "overbought"}:
            await update.message.reply_text("RSI durumu: oversold | overbought")
            return
        rule["state"] = state
        desc = f"RSI {state}"
    elif mode == "macd":
        if len(context.args) < 3:
            await update.message.reply_text("Kullanım: /alert THYAO macd bullish|bearish")
            return
        direction = context.args[2].lower().strip()
        if direction not in {"bullish", "bearish"}:
            await update.message.reply_text("MACD yönü: bullish | bearish")
            return
        rule["direction"] = direction
        desc = f"MACD {direction} cross"
    elif mode == "ma":
        if len(context.args) < 3:
            await update.message.reply_text("Kullanım: /alert THYAO ma golden|death")
            return
        direction = context.args[2].lower().strip()
        if direction not in {"golden", "death"}:
            await update.message.reply_text("MA yönü: golden | death")
            return
        rule["direction"] = direction
        desc = f"MA {direction} cross"
    elif mode == "change":
        if len(context.args) < 3:
            await update.message.reply_text("Kullanım: /alert THYAO change 3")
            return
        try:
            threshold = float(context.args[2])
        except ValueError:
            await update.message.reply_text("Change için yüzde sayı gir: /alert THYAO change 3")
            return
        if threshold <= 0:
            await update.message.reply_text("Yüzde eşik sıfırdan büyük olmalı.")
            return
        rule["threshold"] = threshold
        desc = f"% değişim >= {threshold:.2f}"
    else:  # volume_spike
        multiplier = 1.8
        if len(context.args) > 2:
            try:
                multiplier = float(context.args[2])
            except ValueError:
                await update.message.reply_text("volume_spike çarpanı sayı olmalı. Örn: /alert THYAO volume_spike 2.0")
                return
            if multiplier <= 1:
                await update.message.reply_text("volume_spike çarpanı 1'den büyük olmalı.")
                return
        rule["multiplier"] = multiplier
        desc = f"Hacim spike >= {multiplier:.2f}x"

    saved, added = add_chat_advanced_alert(user_id, symbol, rule)
    if not added:
        await update.message.reply_text(f"ℹ️ {symbol} için aynı gelişmiş alarm zaten var.")
        return
    if saved:
        await update.message.reply_text(f"🔔 Gelişmiş alarm eklendi: {symbol} | {desc}")
    else:
        await update.message.reply_text("❌ Kaydedilemedi.")


# ── /alerts ───────────────────────────────────────────────────

@guard
async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    alerts = get_chat_alerts(user_id)
    adv_alerts = get_chat_advanced_alerts(user_id)

    if not alerts and not adv_alerts:
        await update.message.reply_text("Aktif alarm yok.")
        return

    lines = ["🔔 *Aktif Alarmlar:*"]
    if alerts:
        lines.append("\n*Fiyat Alarmları*")
        for sym, rules in sorted(alerts.items()):
            parts = [f"{'üst' if k=='above' else 'alt'} {v:.2f} TL" for k, v in sorted(rules.items())]
            lines.append(f"• {sym}: {', '.join(parts)}")

    if adv_alerts:
        lines.append("\n*Gelişmiş Alarmlar*")
        for sym, rules in sorted(adv_alerts.items()):
            for rule in rules:
                t = str(rule.get("type", ""))
                if t == "rsi":
                    desc = f"RSI {rule.get('state')}"
                elif t == "macd":
                    desc = f"MACD {rule.get('direction')} cross"
                elif t == "ma":
                    desc = f"MA {rule.get('direction')} cross"
                elif t == "score":
                    desc = f"Score >= {float(rule.get('threshold', 0)):.0f}"
                elif t == "signal":
                    desc = f"Signal {str(rule.get('signal', '')).replace('_', ' ').title()}"
                elif t == "change":
                    desc = f"% değişim >= {float(rule.get('threshold', 0)):.2f}"
                elif t == "volume_spike":
                    desc = f"hacim spike >= {float(rule.get('multiplier', 1.8)):.2f}x"
                else:
                    desc = t
                lines.append(f"• {sym}: {desc}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /clear_alert ──────────────────────────────────────────────

@guard
async def cmd_clear_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /clear_alert THYAO [above|below]")
        return
    symbol = normalize_symbol(context.args[0])
    side = None
    adv_type = None
    if len(context.args) > 1:
        token = context.args[1].lower().strip()
        side = DIRECTION_MAP.get(token)
        if side is None:
            if token in ADV_TYPES:
                adv_type = token
            else:
                await update.message.reply_text("Yön/tip: above | below | rsi | macd | ma | change | volume_spike | score | signal")
                return

    user_id = _get_user_id(update)
    if adv_type is not None:
        saved, cleared = clear_chat_advanced_alert(user_id, symbol, adv_type)
        if not cleared:
            await update.message.reply_text(f"{symbol} {adv_type} alarmı bulunamadı.")
            return
        msg = f"✅ {symbol} {adv_type} gelişmiş alarmları silindi."
    else:
        saved_price, cleared_price = clear_chat_alert(user_id, symbol, side)
        saved_adv, cleared_adv = (True, False)
        if side is None:
            saved_adv, cleared_adv = clear_chat_advanced_alert(user_id, symbol, None)

        if side is None:
            saved = saved_price and saved_adv
            cleared = cleared_price or cleared_adv
            msg = f"✅ {symbol} tüm alarmları silindi."
        else:
            saved = saved_price
            cleared = cleared_price
            msg = f"✅ {symbol} {side} alarmı silindi."

        if not cleared:
            if side is None:
                await update.message.reply_text(f"{symbol} için alarm yok.")
            else:
                await update.message.reply_text(f"{symbol} {side} alarmı bulunamadı.")
            return

    if saved:
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("❌ Kaydedilemedi.")


# ── /start_alerts & /stop_alerts ──────────────────────────────

@guard
async def cmd_start_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = _get_user_id(update)
    name = f"alert-{chat_id}"
    for job in context.job_queue.get_jobs_by_name(name):
        job.schedule_removal()
    context.job_queue.run_repeating(
        alert_job,
        interval=ALERT_INTERVAL_SECONDS,
        first=5,
        chat_id=chat_id,
        data={"user_id": user_id},
        name=name,
    )
    await update.message.reply_text("✅ 15 dakikalık otomatik kontrol başlatıldı.")


@guard
async def cmd_stop_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    name = f"alert-{chat_id}"
    jobs = context.job_queue.get_jobs_by_name(name)
    if not jobs:
        await update.message.reply_text("Aktif kontrol bulunamadı.")
        return
    for job in jobs:
        job.schedule_removal()
    await update.message.reply_text("⛔ Otomatik kontrol durduruldu.")


# ── /daily on|off ───────────────────────────────────────────

@guard
async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args or args[0].lower() not in {"on", "off"}:
        await update.message.reply_text("Kullanım: /daily on|off")
        return

    chat_id = update.effective_chat.id
    user_id = _get_user_id(update)
    name = f"daily-{chat_id}"
    action = args[0].lower()

    if action == "on":
        for job in context.job_queue.get_jobs_by_name(name):
            job.schedule_removal()
        context.job_queue.run_daily(
            daily_report_job,
            time=datetime.strptime("09:30", "%H:%M").time(),
            chat_id=chat_id,
            data={"user_id": user_id},
            name=name,
        )
        await update.message.reply_text("✅ Günlük rapor aktif. Her gün 09:30'da gönderilecek.")
    else:
        jobs = context.job_queue.get_jobs_by_name(name)
        if not jobs:
            await update.message.reply_text("Günlük rapor zaten kapalı.")
            return
        for job in jobs:
            job.schedule_removal()
        await update.message.reply_text("⛔ Günlük rapor kapatıldı.")


# ── unknown command ───────────────────────────────────────────

@guard
async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Bilinmeyen komut. /start yaz.")
