import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

from database import (
    get_monthly_category_summary,
    get_or_create_user,
)


logger = logging.getLogger(__name__)

MALAYSIA_TIMEZONE = ZoneInfo(
    "Asia/Kuching"
)

MONTH_NAMES = {
    1: "Januari",
    2: "Februari",
    3: "Mac",
    4: "April",
    5: "Mei",
    6: "Jun",
    7: "Julai",
    8: "Ogos",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Disember",
}


def format_receipt_count(
    receipt_count: int,
) -> str:
    """Format bilangan resit."""

    return f"{receipt_count} resit"


def format_monthly_summary(
    summary: dict,
) -> str:
    """Sediakan mesej ringkasan bulanan."""

    month_name = MONTH_NAMES[
        summary["month"]
    ]

    year = summary["year"]
    categories = summary["categories"]

    if not categories:
        return (
            f"📊 Ringkasan {month_name} {year}\n\n"
            "Belum ada perbelanjaan direkodkan "
            "untuk bulan ini.\n\n"
            "Hantar gambar resit untuk mula "
            "merekod perbelanjaan."
        )

    category_sections: list[str] = []

    for category_data in categories:
        category = category_data[
            "category"
        ]

        total = category_data[
            "total"
        ]

        receipt_count = category_data[
            "receipt_count"
        ]

        category_sections.append(
            f"📂 {category}\n"
            f"RM{total:,.2f} • "
            f"{format_receipt_count(receipt_count)}"
        )

    return (
        f"📊 Ringkasan {month_name} {year}\n\n"
        + "\n\n".join(category_sections)
        + "\n\n──────────────\n"
        + "💰 Jumlah\n"
        + f"RM{summary['total_spending']:,.2f}\n\n"
        + "🧾 Jumlah resit\n"
        + f"{summary['receipt_count']}"
    )


async def summary_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Paparkan ringkasan perbelanjaan bulan semasa."""

    if update.message is None:
        return

    telegram_user = update.effective_user

    if telegram_user is None:
        await update.message.reply_text(
            "Maklumat pengguna tidak dapat dibaca."
        )
        return

    status_message = await update.message.reply_text(
        "⏳ Menyediakan ringkasan..."
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

        monthly_summary = await asyncio.to_thread(
            get_monthly_category_summary,
            telegram_user.id,
            today,
        )

        await status_message.edit_text(
            format_monthly_summary(
                monthly_summary
            )
        )

    except Exception as error:
        logger.exception(
            "Gagal menyediakan ringkasan: %s",
            error,
        )

        await status_message.edit_text(
            "Ringkasan gagal dipaparkan.\n\n"
            "Sila cuba semula."
        )