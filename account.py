import asyncio
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

from database import (
    get_account_summary,
    get_or_create_user,
)
from plans import PlanCode
from subscription_service import (
    SubscriptionContext,
    get_subscription_context,
)
from usage import get_monthly_plan_usage


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


def parse_created_at(
    created_at: Any,
) -> datetime | None:
    """Tukar tarikh Supabase kepada objek datetime."""

    if not isinstance(
        created_at,
        str,
    ):
        return None

    normalized_value = created_at.replace(
        "Z",
        "+00:00",
    )

    try:
        return datetime.fromisoformat(
            normalized_value
        )
    except ValueError:
        return None


def format_datetime_date(
    value: datetime | None,
) -> str:
    """Format objek datetime kepada tarikh Bahasa Melayu."""

    if value is None:
        return "Tiada"

    local_date = value.astimezone(
        MALAYSIA_TIMEZONE
    )

    month_name = MONTH_NAMES[
        local_date.month
    ]

    return (
        f"{local_date.day} "
        f"{month_name} "
        f"{local_date.year}"
    )


def format_registration_date(
    created_at: Any,
) -> str:
    """Format tarikh pendaftaran pengguna."""

    parsed_date = parse_created_at(
        created_at
    )

    if parsed_date is None:
        return "Tidak diketahui"

    return format_datetime_date(
        parsed_date
    )


def get_plan_icon(
    plan_code: PlanCode,
) -> str:
    """Dapatkan ikon pelan."""

    if plan_code == PlanCode.STARTER:
        return "⭐"

    if plan_code == PlanCode.BUSINESS:
        return "⭐⭐"

    return "🆓"


def format_monthly_price(
    subscription: SubscriptionContext,
) -> str:
    """Format harga bulanan pelan."""

    price = subscription.plan.monthly_price_rm

    if price == 0:
        return "RM0"

    return f"RM{price:.2f} / bulan"


def build_usage_bar(
    monthly_usage: int,
    monthly_limit: int,
) -> str:
    """Bina indikator ringkas penggunaan pelan."""

    if monthly_limit <= 0:
        return "░░░░░░░░░░"

    safe_usage = min(
        monthly_usage,
        monthly_limit,
    )

    filled_blocks = round(
        (
            safe_usage
            / monthly_limit
        )
        * 10
    )

    empty_blocks = 10 - filled_blocks

    return (
        "▓" * filled_blocks
        + "░" * empty_blocks
    )


def format_usage_status(
    monthly_usage: int,
    monthly_limit: int,
) -> str:
    """Sediakan status baki penggunaan resit."""

    remaining_receipts = max(
        monthly_limit - monthly_usage,
        0,
    )

    if remaining_receipts == 0:
        return "Had bulanan telah digunakan."

    return (
        f"{remaining_receipts} resit lagi tersedia."
    )


def format_subscription_period(
    subscription: SubscriptionContext,
) -> str:
    """Format tempoh langganan."""

    start_date = format_datetime_date(
        subscription.starts_at
    )

    if subscription.expires_at is None:
        return (
            f"Mula\n{start_date}\n\n"
            "Tamat\nTiada tarikh tamat"
        )

    end_date = format_datetime_date(
        subscription.expires_at
    )

    return (
        f"Mula\n{start_date}\n\n"
        f"Tamat\n{end_date}"
    )


def format_active_addons(
    subscription: SubscriptionContext,
) -> str:
    """Format senarai add-on aktif."""

    if not subscription.active_addons:
        return "Tiada"

    addon_lines: list[str] = []

    for active_addon in subscription.active_addons:
        addon_name = active_addon.addon.name

        if active_addon.quantity > 1:
            addon_name = (
                f"{addon_name} "
                f"x{active_addon.quantity}"
            )

        addon_lines.append(
            f"• {addon_name}"
        )

    return "\n".join(
        addon_lines
    )


def format_account_message(
    summary: dict[str, Any],
    subscription: SubscriptionContext,
    telegram_id: int,
    fallback_name: str,
    monthly_plan_usage: int,
) -> str:
    """Sediakan paparan maklumat akaun."""

    user = summary["user"]

    name = (
        user.get("name")
        or fallback_name
        or "Pengguna"
    )

    registered_at = format_registration_date(
        user.get("created_at")
    )

    monthly_limit = (
        subscription.monthly_receipt_limit
    )

    usage_bar = build_usage_bar(
        monthly_usage=monthly_plan_usage,
        monthly_limit=monthly_limit,
    )

    usage_status = format_usage_status(
        monthly_usage=monthly_plan_usage,
        monthly_limit=monthly_limit,
    )

    plan_icon = get_plan_icon(
        subscription.plan_code
    )

    monthly_price = format_monthly_price(
        subscription
    )

    subscription_period = (
        format_subscription_period(
            subscription
        )
    )

    active_addons = format_active_addons(
        subscription
    )

    return (
        "👤 Akaun\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Nama\n"
        f"{name}\n\n"
        "Telegram ID\n"
        f"{telegram_id}\n\n"
        "Pelan\n"
        f"{plan_icon} {subscription.plan.name}\n\n"
        "Harga\n"
        f"{monthly_price}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Daftar\n"
        f"{registered_at}\n\n"
        "Langganan\n"
        f"{subscription_period}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Penggunaan Pelan Bulan Ini\n"
        f"{monthly_plan_usage} / "
        f"{monthly_limit} resit\n"
        f"{usage_bar}\n\n"
        f"{usage_status}\n\n"
        "Jumlah Resit Disimpan\n"
        f"{summary['total_receipt_count']}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Add-on Aktif\n"
        f"{active_addons}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Status\n"
        f"{subscription.status} ✅"
    )


async def account_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Paparkan maklumat akaun pengguna."""

    if update.message is None:
        return

    telegram_user = update.effective_user

    if telegram_user is None:
        await update.message.reply_text(
            "Maklumat pengguna tidak dapat dibaca."
        )
        return

    status_message = await update.message.reply_text(
        "⏳ Menyediakan maklumat akaun..."
    )

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

        account_summary = await asyncio.to_thread(
            get_account_summary,
            telegram_user.id,
            today,
        )

        subscription = await asyncio.to_thread(
            get_subscription_context,
            telegram_user.id,
        )

        monthly_plan_usage = (
            await asyncio.to_thread(
                get_monthly_plan_usage,
                telegram_user.id,
                today,
            )
        )

        await status_message.edit_text(
            format_account_message(
                summary=account_summary,
                subscription=subscription,
                telegram_id=telegram_user.id,
                fallback_name=name,
                monthly_plan_usage=(
                    monthly_plan_usage
                ),
            )
        )

    except Exception as error:
        logger.exception(
            "Gagal menyediakan maklumat akaun: %s",
            error,
        )

        await status_message.edit_text(
            "Maklumat akaun gagal dipaparkan.\n\n"
            "Sila cuba semula."
        )