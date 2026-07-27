import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

from database import (
    get_dashboard_summary,
    get_or_create_user,
)


logger = logging.getLogger(__name__)

MALAYSIA_TIMEZONE = ZoneInfo(
    "Asia/Kuching"
)


def format_dashboard(
    summary: dict,
) -> str:
    """Sediakan mesej dashboard pengguna."""

    top_category = summary["top_category"]
    top_category_total = summary[
        "top_category_total"
    ]

    if top_category is None:
        category_text = "Belum ada data"
    else:
        category_text = (
            f"{top_category}\n"
            f"RM{top_category_total:,.2f}"
        )

    return (
        "📊 Dashboard Perbelanjaan\n\n"
        "──────────────\n"
        "💰 Hari ini\n"
        f"RM{summary['today_total']:,.2f}\n\n"
        "📅 Bulan ini\n"
        f"RM{summary['month_total']:,.2f}\n\n"
        "🧾 Jumlah resit bulan ini\n"
        f"{summary['month_receipt_count']}\n\n"
        "📂 Kategori tertinggi\n"
        f"{category_text}\n"
        "──────────────"
    )


async def dashboard_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Paparkan dashboard perbelanjaan pengguna."""

    if update.message is None:
        return

    telegram_user = update.effective_user

    if telegram_user is None:
        await update.message.reply_text(
            "Maklumat pengguna tidak dapat dibaca."
        )
        return

    status_message = await update.message.reply_text(
        "⏳ Menyediakan dashboard..."
    )

    try:
        name = telegram_user.first_name or "Pengguna"

        await asyncio.to_thread(
            get_or_create_user,
            telegram_user.id,
            name,
        )

        today = datetime.now(
            MALAYSIA_TIMEZONE
        ).date()

        summary = await asyncio.to_thread(
            get_dashboard_summary,
            telegram_user.id,
            today,
        )

        await status_message.edit_text(
            format_dashboard(summary)
        )

    except Exception as error:
        logger.exception(
            "Gagal menyediakan dashboard: %s",
            error,
        )

        await status_message.edit_text(
            "Dashboard gagal dipaparkan.\n\n"
            "Sila cuba semula."
        )