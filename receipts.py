import asyncio
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from database import (
    get_or_create_user,
    get_recent_receipts,
)


logger = logging.getLogger(__name__)

MONTH_NAMES = {
    1: "Jan",
    2: "Feb",
    3: "Mac",
    4: "Apr",
    5: "Mei",
    6: "Jun",
    7: "Jul",
    8: "Ogos",
    9: "Sep",
    10: "Okt",
    11: "Nov",
    12: "Dis",
}


def format_receipt_date(
    receipt_date: str,
) -> str:
    """Tukar tarikh ISO kepada paparan ringkas."""

    try:
        parsed_date = datetime.strptime(
            receipt_date,
            "%Y-%m-%d",
        )

        month_name = MONTH_NAMES[
            parsed_date.month
        ]

        return (
            f"{parsed_date.day} "
            f"{month_name} "
            f"{parsed_date.year}"
        )

    except (
        TypeError,
        ValueError,
    ):
        return "Tarikh tidak diketahui"


def format_recent_receipts(
    receipts: list[dict],
) -> str:
    """Sediakan mesej senarai resit terkini."""

    if not receipts:
        return (
            "🧾 Resit Terkini\n\n"
            "Belum ada resit disimpan.\n\n"
            "Hantar gambar resit untuk mula "
            "merekod perbelanjaan."
        )

    receipt_sections: list[str] = []

    for index, receipt in enumerate(
        receipts,
        start=1,
    ):
        merchant = (
            receipt.get("merchant")
            or "Peniaga tidak diketahui"
        )

        category = (
            receipt.get("category")
            or "Lain-lain"
        )

        receipt_date = format_receipt_date(
            receipt.get("receipt_date", "")
        )

        raw_total = receipt.get(
            "total",
            0,
        )

        try:
            total = float(raw_total)
        except (
            TypeError,
            ValueError,
        ):
            total = 0.0

        receipt_sections.append(
            f"{index}. {merchant}\n"
            f"   💰 RM{total:,.2f}\n"
            f"   📅 {receipt_date}\n"
            f"   📂 {category}"
        )

    return (
        "🧾 Resit Terkini\n\n"
        + "\n\n──────────────\n\n".join(
            receipt_sections
        )
        + "\n\nPaparan maksimum 10 resit terkini."
    )


async def receipts_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Paparkan maksimum 10 resit terkini pengguna."""

    if update.message is None:
        return

    telegram_user = update.effective_user

    if telegram_user is None:
        await update.message.reply_text(
            "Maklumat pengguna tidak dapat dibaca."
        )
        return

    status_message = await update.message.reply_text(
        "⏳ Mencari resit terkini..."
    )

    try:
        name = telegram_user.first_name or "Pengguna"

        await asyncio.to_thread(
            get_or_create_user,
            telegram_user.id,
            name,
        )

        recent_receipts = await asyncio.to_thread(
            get_recent_receipts,
            telegram_user.id,
            10,
        )

        await status_message.edit_text(
            format_recent_receipts(
                recent_receipts
            )
        )

    except Exception as error:
        logger.exception(
            "Gagal memaparkan resit terkini: %s",
            error,
        )

        await status_message.edit_text(
            "Resit terkini gagal dipaparkan.\n\n"
            "Sila cuba semula."
        )