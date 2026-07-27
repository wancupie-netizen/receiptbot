import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

from bot import receive_receipt
from database import get_or_create_user
from plans import (
    FREE_PLAN_MONTHLY_LIMIT,
)
from usage import get_monthly_plan_usage


logger = logging.getLogger(__name__)

MALAYSIA_TIMEZONE = ZoneInfo(
    "Asia/Kuching"
)


def format_limit_reached_message() -> str:
    """Sediakan mesej apabila had Free telah digunakan."""

    return (
        "⚠️ Had Pelan Free Telah Digunakan\n\n"
        "Pelan Free membenarkan sehingga "
        f"{FREE_PLAN_MONTHLY_LIMIT} resit "
        "setiap bulan.\n\n"
        f"Penggunaan bulan ini:\n"
        f"{FREE_PLAN_MONTHLY_LIMIT} / "
        f"{FREE_PLAN_MONTHLY_LIMIT} resit\n\n"
        "Upgrade ke ReceiptBot PRO untuk "
        "terus menyimpan resit tanpa had.\n\n"
        "Ciri langganan PRO akan tersedia "
        "tidak lama lagi."
    )


async def receive_receipt_with_plan_check(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Semak had pelan sebelum memproses gambar resit.

    Jika pengguna masih mempunyai kuota, teruskan kepada
    flow receive_receipt asal.
    """

    if update.message is None:
        return

    telegram_user = update.effective_user

    if telegram_user is None:
        await update.message.reply_text(
            "Maklumat pengguna tidak dapat dibaca."
        )
        return

    try:
        name = (
            telegram_user.first_name
            or "Pengguna"
        )

        await asyncio.to_thread(
            get_or_create_user,
            telegram_user.id,
            name,
        )

        today = datetime.now(
            MALAYSIA_TIMEZONE
        ).date()

        monthly_usage = await asyncio.to_thread(
            get_monthly_plan_usage,
            telegram_user.id,
            today,
        )

        if (
            monthly_usage
            >= FREE_PLAN_MONTHLY_LIMIT
        ):
            logger.info(
                "Had Free Plan dicapai. "
                "Telegram ID: %s | Penggunaan: %s",
                telegram_user.id,
                monthly_usage,
            )

            await update.message.reply_text(
                format_limit_reached_message()
            )
            return

        await receive_receipt(
            update,
            context,
        )

    except Exception as error:
        logger.exception(
            "Gagal menyemak penggunaan pelan: %s",
            error,
        )

        await update.message.reply_text(
            "ReceiptBot gagal menyemak "
            "penggunaan akaun anda.\n\n"
            "Sila cuba semula."
        )