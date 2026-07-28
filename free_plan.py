import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

from bot import receive_receipt
from database import get_or_create_user
from subscription_service import (
    SubscriptionContext,
    get_subscription_context,
)
from usage import get_monthly_plan_usage


logger = logging.getLogger(__name__)

MALAYSIA_TIMEZONE = ZoneInfo(
    "Asia/Kuching"
)


def format_plan_price(
    subscription: SubscriptionContext,
) -> str:
    """Format harga bulanan pelan."""

    price = subscription.plan.monthly_price_rm

    if price == 0:
        return "RM0"

    return f"RM{price:.2f} / bulan"


def format_limit_reached_message(
    subscription: SubscriptionContext,
    monthly_usage: int,
) -> str:
    """Sediakan mesej apabila had pelan telah digunakan."""

    plan_name = subscription.plan.name
    monthly_limit = (
        subscription.monthly_receipt_limit
    )

    if plan_name == "Free":
        upgrade_message = (
            "Naik taraf ke Starter atau Business "
            "untuk mendapatkan kuota resit yang lebih tinggi.\n\n"
            "⭐ Starter\n"
            "100 resit / bulan\n"
            "RM9.90 / bulan\n\n"
            "⭐⭐ Business\n"
            "500 resit / bulan\n"
            "RM19.90 / bulan"
        )

    elif plan_name == "Starter":
        upgrade_message = (
            "Naik taraf ke Business untuk mendapatkan:\n\n"
            "✅ 500 resit setiap bulan\n"
            "✅ Eksport Excel dan PDF\n"
            "✅ Kategori tersuai\n"
            "✅ Rekod pendapatan dan perbelanjaan\n\n"
            "⭐⭐ Business\n"
            "RM19.90 / bulan"
        )

    else:
        upgrade_message = (
            "Kuota pelan Business anda telah digunakan.\n\n"
            "Add-on tambahan resit akan tersedia "
            "tidak lama lagi."
        )

    return (
        f"⚠️ Had Pelan {plan_name} Telah Digunakan\n\n"
        f"Pelan {plan_name} membenarkan sehingga "
        f"{monthly_limit} resit setiap bulan.\n\n"
        "Penggunaan bulan ini\n"
        f"{monthly_usage} / {monthly_limit} resit\n\n"
        f"{upgrade_message}"
    )


def format_usage_warning_message(
    subscription: SubscriptionContext,
    monthly_usage: int,
) -> str | None:
    """Sediakan amaran jika kuota hampir digunakan."""

    monthly_limit = (
        subscription.monthly_receipt_limit
    )

    remaining = max(
        monthly_limit - monthly_usage,
        0,
    )

    if remaining <= 0:
        return None

    warning_threshold = max(
        round(monthly_limit * 0.10),
        2,
    )

    if remaining > warning_threshold:
        return None

    return (
        "⚠️ Kuota resit hampir habis\n\n"
        f"Pelan: {subscription.plan.name}\n"
        f"Penggunaan: {monthly_usage} / "
        f"{monthly_limit} resit\n"
        f"Baki: {remaining} resit"
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

        subscription = await asyncio.to_thread(
            get_subscription_context,
            telegram_user.id,
        )

        monthly_usage = await asyncio.to_thread(
            get_monthly_plan_usage,
            telegram_user.id,
            today,
        )

        monthly_limit = (
            subscription.monthly_receipt_limit
        )

        if monthly_usage >= monthly_limit:
            logger.info(
                "Had pelan dicapai. "
                "Telegram ID: %s | "
                "Pelan: %s | "
                "Penggunaan: %s | "
                "Had: %s",
                telegram_user.id,
                subscription.plan_code.value,
                monthly_usage,
                monthly_limit,
            )

            await update.message.reply_text(
                format_limit_reached_message(
                    subscription=subscription,
                    monthly_usage=monthly_usage,
                )
            )
            return

        usage_warning = format_usage_warning_message(
            subscription=subscription,
            monthly_usage=monthly_usage,
        )

        if usage_warning is not None:
            await update.message.reply_text(
                usage_warning
            )

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