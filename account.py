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
from plans import (
    FREE_PLAN_MONTHLY_LIMIT,
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


def format_registration_date(
    created_at: Any,
) -> str:
    """Format tarikh pendaftaran pengguna."""

    parsed_date = parse_created_at(
        created_at
    )

    if parsed_date is None:
        return "Tidak diketahui"

    local_date = parsed_date.astimezone(
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


def build_usage_bar(
    monthly_usage: int,
) -> str:
    """Bina indikator ringkas penggunaan pelan."""

    safe_usage = min(
        monthly_usage,
        FREE_PLAN_MONTHLY_LIMIT,
    )

    filled_blocks = round(
        (
            safe_usage
            / FREE_PLAN_MONTHLY_LIMIT
        )
        * 10
    )

    empty_blocks = 10 - filled_blocks

    return (
        "▓" * filled_blocks
        + "░" * empty_blocks
    )


def format_account_message(
    summary: dict[str, Any],
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

    plan = summary.get(
        "plan",
        "Free",
    )

    status = summary.get(
        "status",
        "Aktif",
    )

    remaining_receipts = max(
        FREE_PLAN_MONTHLY_LIMIT
        - monthly_plan_usage,
        0,
    )

    usage_bar = build_usage_bar(
        monthly_plan_usage
    )

    if remaining_receipts == 0:
        usage_status = (
            "Had bulanan telah digunakan."
        )
    else:
        usage_status = (
            f"{remaining_receipts} resit lagi tersedia."
        )

    return (
        "👤 Akaun\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Nama\n"
        f"{name}\n\n"
        "Telegram ID\n"
        f"{telegram_id}\n\n"
        "Pelan\n"
        f"🆓 {plan}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Daftar\n"
        f"{registered_at}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Penggunaan Pelan Bulan Ini\n"
        f"{monthly_plan_usage} / "
        f"{FREE_PLAN_MONTHLY_LIMIT} resit\n"
        f"{usage_bar}\n\n"
        f"{usage_status}\n\n"
        "Jumlah Resit Disimpan\n"
        f"{summary['total_receipt_count']}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Status\n"
        f"{status} ✅"
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