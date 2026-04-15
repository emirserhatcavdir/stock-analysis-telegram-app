"""Daily report generation and scheduled report job."""

from __future__ import annotations

from telegram.ext import ContextTypes

from stock_bot.data_manager import get_chat_watchlist, load_portfolio, load_trades
from stock_bot.portfolio_analytics import compute_portfolio_analytics, get_losers, get_winners
from stock_bot.scanner import ScanReport, run_scan


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def _format_scan_trigger_lines(title: str, report: ScanReport | None, limit: int = 4) -> list[str]:
    lines = [title]
    if report is None or report.analyzed_count == 0:
        lines.append("• veri yok")
        return lines

    signals: list[str] = []

    for x in report.oversold[:limit]:
        rsi = x.rsi if x.rsi is not None else 0
        signals.append(f"• {x.symbol}: RSI oversold ({rsi:.2f})")

    for x in report.overbought[:limit]:
        rsi = x.rsi if x.rsi is not None else 0
        signals.append(f"• {x.symbol}: RSI overbought ({rsi:.2f})")

    for x in report.golden_cross[:limit]:
        signals.append(f"• {x.symbol}: MA golden cross")

    for x in report.death_cross[:limit]:
        signals.append(f"• {x.symbol}: MA death cross")

    for x in report.volume_spikes[:limit]:
        ratio = x.volume_ratio if x.volume_ratio is not None else 0
        signals.append(f"• {x.symbol}: volume spike ({ratio:.2f}x)")

    if not signals:
        lines.append("• güçlü tetik sinyali yok")
    else:
        lines.extend(signals[:limit])

    return lines


def build_daily_report(user_id: int | str) -> str:
    portfolio = load_portfolio(user_id)
    trades = load_trades(user_id)
    watchlist = get_chat_watchlist(user_id)

    lines: list[str] = ["📬 *Günlük Yatırım Raporu*"]

    # 1) Portfolio summary
    if portfolio:
        analytics = compute_portfolio_analytics(portfolio, trades)
        lines.extend(
            [
                "",
                "*💼 Portföy Özeti*",
                f"Pozisyon: {len(analytics.positions)}",
                f"Toplam Değer: {_fmt_money(analytics.total_value)} TL",
                f"Gerçekleşmemiş K/Z: {analytics.unrealized_pnl:+,.2f} TL",
                f"Gerçekleşmiş K/Z: {analytics.realized_pnl:+,.2f} TL",
                f"Net K/Z: {analytics.net_pnl:+,.2f} TL",
            ]
        )

        # 2) Top movers
        winners = get_winners(analytics, limit=3)
        losers = get_losers(analytics, limit=3)

        lines.append("")
        lines.append("*🚀 Top Movers*")
        if winners:
            lines.append("Kazananlar:")
            for p in winners:
                lines.append(f"• {p.symbol}: {p.unrealized_pct:+.2f}%")
        else:
            lines.append("Kazananlar: veri yok")

        if losers:
            lines.append("Kaybedenler:")
            for p in losers:
                lines.append(f"• {p.symbol}: {p.unrealized_pct:+.2f}%")
        else:
            lines.append("Kaybedenler: veri yok")

        # 3) Scan results + triggered signals on portfolio
        portfolio_symbols = sorted(portfolio.keys())
        report_portfolio = run_scan("portfolio", portfolio_symbols=portfolio_symbols)
        lines.append("")
        lines.extend(_format_scan_trigger_lines("*🔎 Portföy Scan Tetikleri*", report_portfolio))
    else:
        lines.extend(["", "*💼 Portföy Özeti*", "• Portföy boş"])

    # 4) Watchlist scan results
    if watchlist:
        report_watchlist = run_scan("watchlist", watchlist_symbols=watchlist)
        lines.append("")
        lines.extend(_format_scan_trigger_lines("*👀 Watchlist Scan Tetikleri*", report_watchlist))
    else:
        lines.extend(["", "*👀 Watchlist Scan Tetikleri*", "• Watchlist boş"])

    return "\n".join(lines)


async def daily_report_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id: int = context.job.chat_id
    user_id: int = int((context.job.data or {}).get("user_id", chat_id))
    text = build_daily_report(user_id)
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
