from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from database import (
    get_user_by_telegram_id,
    supabase,
)


MALAYSIA_TIMEZONE = ZoneInfo(
    "Asia/Kuching"
)


def get_month_boundaries_utc(
    today: date,
) -> tuple[datetime, datetime]:
    """
    Dapatkan sempadan awal dan akhir bulan Malaysia
    dalam timezone UTC.
    """

    start_local = datetime(
        year=today.year,
        month=today.month,
        day=1,
        tzinfo=MALAYSIA_TIMEZONE,
    )

    if today.month == 12:
        end_local = datetime(
            year=today.year + 1,
            month=1,
            day=1,
            tzinfo=MALAYSIA_TIMEZONE,
        )
    else:
        end_local = datetime(
            year=today.year,
            month=today.month + 1,
            day=1,
            tzinfo=MALAYSIA_TIMEZONE,
        )

    start_utc = start_local.astimezone(
        timezone.utc
    )

    end_utc = end_local.astimezone(
        timezone.utc
    )

    return start_utc, end_utc


def get_monthly_plan_usage(
    telegram_id: int,
    today: date,
) -> int:
    """
    Kira bilangan resit yang disimpan pada bulan semasa.

    Pengiraan menggunakan created_at supaya had pelan
    berdasarkan masa resit dimuat naik, bukan tarikh resit.
    """

    user = get_user_by_telegram_id(
        telegram_id
    )

    user_id = user.get("id")

    if user_id is None:
        raise RuntimeError(
            "User ID tidak dijumpai."
        )

    start_utc, end_utc = (
        get_month_boundaries_utc(today)
    )

    response = (
        supabase.table("receipts")
        .select("id")
        .eq("user_id", user_id)
        .gte(
            "created_at",
            start_utc.isoformat(),
        )
        .lt(
            "created_at",
            end_utc.isoformat(),
        )
        .execute()
    )

    receipts: list[dict[str, Any]] = (
        response.data or []
    )

    return len(receipts)