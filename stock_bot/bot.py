#!/usr/bin/env python3
"""Entry point – wires commands to the Telegram application and starts polling."""

from __future__ import annotations

import logging
import sys

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from stock_bot.commands import (
    cmd_add,
    cmd_alert,
    cmd_alerts,
    cmd_analyze,
    cmd_buy,
    cmd_bist,
    cmd_chart,
    cmd_comment,
    cmd_commentary,
    cmd_clear_alert,
    cmd_daily,
    cmd_fundamental,
    cmd_fundamentals,
    cmd_losers,
    cmd_market,
    cmd_movers,
    cmd_allocation,
    cmd_portfolio,
    cmd_performance,
    cmd_price,
    cmd_rank,
    cmd_remove,
    cmd_scan,
    cmd_score,
    cmd_sell,
    cmd_summary,
    cmd_start,
    cmd_start_alerts,
    cmd_stop_alerts,
    cmd_trades,
    cmd_unwatch,
    cmd_unknown,
    cmd_volumeleaders,
    cmd_watch,
    cmd_watchlist_add,
    cmd_watchlist_remove,
    cmd_winners,
    cmd_watchlist,
)
from stock_bot.config import TOKEN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


async def _error_handler(update, context):
    logger.exception("Unhandled error", exc_info=context.error)


def main() -> None:
    if not TOKEN:
        print("ERROR: Set TELEGRAM_BOT_TOKEN environment variable first.")
        sys.exit(1)

    app = ApplicationBuilder().token(TOKEN).build()

    # English + Turkish aliases for every command
    _handlers = {
        "start":        cmd_start,
        # Portfolio
        "add":          cmd_add,
        "ekle":         cmd_add,
        "remove":       cmd_remove,
        "cikar":        cmd_remove,
        "portfolio":    cmd_portfolio,
        "liste":        cmd_portfolio,
        "buy":          cmd_buy,
        "al":           cmd_buy,
        "sell":         cmd_sell,
        "sat":          cmd_sell,
        "trades":       cmd_trades,
        "islemler":     cmd_trades,
        "summary":      cmd_summary,
        "ozet":         cmd_summary,
        "performance":  cmd_performance,
        "performans":   cmd_performance,
        "allocation":   cmd_allocation,
        "dagilim":      cmd_allocation,
        "winners":      cmd_winners,
        "kazananlar":   cmd_winners,
        "losers":       cmd_losers,
        "kaybedenler":  cmd_losers,
        # Analysis
        "price":        cmd_price,
        "fiyat":        cmd_price,
        "score":        cmd_score,
        "puan":         cmd_score,
        "rank":         cmd_rank,
        "sirala":       cmd_rank,
        "analyze":      cmd_analyze,
        "analiz":       cmd_analyze,
        "chart":        cmd_chart,
        "grafik":       cmd_chart,
        "scan":         cmd_scan,
        "tarama":       cmd_scan,
        "market":       cmd_market,
        "piyasa":       cmd_market,
        "bist":         cmd_bist,
        "movers":       cmd_movers,
        "hareketliler": cmd_movers,
        "volumeleaders": cmd_volumeleaders,
        "hacimliderleri": cmd_volumeleaders,
        "fundamental": cmd_fundamental,
        "temel": cmd_fundamental,
        "fundamentals": cmd_fundamentals,
        "temeller": cmd_fundamentals,
        "comment":      cmd_comment,
        "yorum":        cmd_comment,
        "commentary":   cmd_commentary,
        "yorumla":      cmd_commentary,
        # Watchlist
        "watch":        cmd_watch,
        "izle":         cmd_watch,
        "unwatch":      cmd_unwatch,
        "izleme_sil":   cmd_unwatch,
        "watchlist":    cmd_watchlist,
        "watchlist_add": cmd_watchlist_add,
        "watchlist_remove": cmd_watchlist_remove,
        "izleme_listesi": cmd_watchlist,
        # Alerts
        "alert":        cmd_alert,
        "alarm":        cmd_alert,
        "alerts":       cmd_alerts,
        "alarmlar":     cmd_alerts,
        "clear_alert":  cmd_clear_alert,
        "alarm_sil":    cmd_clear_alert,
        "start_alerts": cmd_start_alerts,
        "alarm_kur":    cmd_start_alerts,
        "stop_alerts":  cmd_stop_alerts,
        "alarm_durdur": cmd_stop_alerts,
        "daily":        cmd_daily,
        "gunluk":       cmd_daily,
    }

    for name, handler in _handlers.items():
        app.add_handler(CommandHandler(name, handler))

    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))
    app.add_error_handler(_error_handler)

    logger.info("Bot started ✅")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
