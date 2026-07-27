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


def format_account_message(
    summary: dict[str, Any],
    telegram_id: int,
    fallback_name: str,
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
        "Resit Bulan Ini\n"
        f"{summary['month_receipt_count']}\n\n"
        "Jumlah Resit\n"
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

        await status_message.edit_text(
            format_account_message(
                summary=account_summary,
                telegram_id=telegram_user.id,
                fallback_name=name,
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