import mimetypes
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from supabase import Client, create_client

from config import (
    SUPABASE_SECRET_KEY,
    SUPABASE_URL,
)


STORAGE_BUCKET = "receipts"


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
)


def get_or_create_user(
    telegram_id: int,
    name: str,
) -> tuple[dict[str, Any], bool]:
    """
    Cari pengguna berdasarkan Telegram ID.

    Returns:
        tuple[user_data, is_new_user]
    """

    existing_user = (
        supabase.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .limit(1)
        .execute()
    )

    if existing_user.data:
        return existing_user.data[0], False

    new_user = (
        supabase.table("users")
        .insert(
            {
                "telegram_id": telegram_id,
                "name": name,
            }
        )
        .execute()
    )

    if not new_user.data:
        raise RuntimeError(
            "Supabase tidak memulangkan "
            "data pengguna baharu."
        )

    return new_user.data[0], True


def get_user_by_telegram_id(
    telegram_id: int,
) -> dict[str, Any]:
    """Cari pengguna berdasarkan Telegram ID."""

    response = (
        supabase.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Pengguna tidak dijumpai dalam Supabase."
        )

    return response.data[0]


def build_receipt_storage_path(
    telegram_id: int,
    receipt_date: str,
    image_path: Path,
) -> str:
    """Bina lokasi fail tersusun dalam Storage."""

    try:
        parsed_date = datetime.strptime(
            receipt_date,
            "%Y-%m-%d",
        )

        year = parsed_date.strftime("%Y")
        month = parsed_date.strftime("%m")
        day = parsed_date.strftime("%d")

    except ValueError:
        year = "unknown"
        month = "unknown"
        day = "unknown"

    extension = image_path.suffix.lower()

    if extension not in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }:
        extension = ".jpg"

    filename = (
        f"receipt_{uuid4().hex}{extension}"
    )

    return (
        f"{telegram_id}/"
        f"{year}/"
        f"{month}/"
        f"{day}/"
        f"{filename}"
    )


def get_image_mime_type(
    image_path: Path,
) -> str:
    """Dapatkan MIME type gambar."""

    mime_type, _ = mimetypes.guess_type(
        image_path.name
    )

    if mime_type is None:
        return "image/jpeg"

    return mime_type


def upload_receipt_image(
    telegram_id: int,
    receipt_date: str,
    image_path: str,
) -> str:
    """
    Upload gambar resit ke Supabase Storage.

    Returns:
        Storage path gambar yang berjaya di-upload.
    """

    local_path = Path(image_path)

    if not local_path.exists():
        raise FileNotFoundError(
            f"Gambar lokal tidak dijumpai: {local_path}"
        )

    storage_path = build_receipt_storage_path(
        telegram_id=telegram_id,
        receipt_date=receipt_date,
        image_path=local_path,
    )

    mime_type = get_image_mime_type(
        local_path
    )

    with local_path.open("rb") as image_file:
        supabase.storage.from_(
            STORAGE_BUCKET
        ).upload(
            path=storage_path,
            file=image_file,
            file_options={
                "content-type": mime_type,
                "cache-control": "3600",
                "upsert": "false",
            },
        )

    return storage_path


def create_receipt(
    telegram_id: int,
    merchant: str,
    receipt_date: str,
    total: float,
    category: str,
    storage_path: str,
) -> dict[str, Any]:
    """Simpan rekod perbelanjaan ke jadual receipts."""

    user = get_user_by_telegram_id(
        telegram_id
    )

    user_id = user.get("id")

    if user_id is None:
        raise RuntimeError(
            "User ID tidak dijumpai."
        )

    response = (
        supabase.table("receipts")
        .insert(
            {
                "user_id": user_id,
                "merchant": merchant,
                "receipt_date": receipt_date,
                "total": total,
                "category": category,
                "image_url": storage_path,
                "raw_text": None,
            }
        )
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Supabase tidak memulangkan "
            "rekod resit yang baharu."
        )

    return response.data[0]


def get_dashboard_summary(
    telegram_id: int,
    today: date,
) -> dict[str, Any]:
    """Kira ringkasan perbelanjaan bulan semasa."""

    user = get_user_by_telegram_id(
        telegram_id
    )

    user_id = user.get("id")

    if user_id is None:
        raise RuntimeError(
            "User ID tidak dijumpai."
        )

    first_day = today.replace(
        day=1
    )

    response = (
        supabase.table("receipts")
        .select(
            "id,total,category,receipt_date"
        )
        .eq("user_id", user_id)
        .gte(
            "receipt_date",
            first_day.isoformat(),
        )
        .lte(
            "receipt_date",
            today.isoformat(),
        )
        .order(
            "receipt_date",
            desc=True,
        )
        .execute()
    )

    receipts = response.data or []

    today_total = 0.0
    month_total = 0.0

    category_totals: defaultdict[
        str,
        float,
    ] = defaultdict(float)

    for receipt in receipts:
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

        month_total += total

        if (
            receipt.get("receipt_date")
            == today.isoformat()
        ):
            today_total += total

        category = (
            receipt.get("category")
            or "Lain-lain"
        )

        category_totals[category] += total

    if category_totals:
        top_category = max(
            category_totals,
            key=category_totals.get,
        )

        top_category_total = category_totals[
            top_category
        ]

    else:
        top_category = None
        top_category_total = 0.0

    return {
        "today_total": today_total,
        "month_total": month_total,
        "month_receipt_count": len(receipts),
        "top_category": top_category,
        "top_category_total": top_category_total,
    }


def get_recent_receipts(
    telegram_id: int,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Dapatkan resit terkini pengguna."""

    user = get_user_by_telegram_id(
        telegram_id
    )

    user_id = user.get("id")

    if user_id is None:
        raise RuntimeError(
            "User ID tidak dijumpai."
        )

    safe_limit = max(
        1,
        min(limit, 10),
    )

    response = (
        supabase.table("receipts")
        .select(
            "id,merchant,total,"
            "receipt_date,category,created_at"
        )
        .eq("user_id", user_id)
        .order(
            "receipt_date",
            desc=True,
        )
        .order(
            "created_at",
            desc=True,
        )
        .limit(safe_limit)
        .execute()
    )

    return response.data or []


def get_monthly_category_summary(
    telegram_id: int,
    today: date,
) -> dict[str, Any]:
    """Kira ringkasan bulan semasa mengikut kategori."""

    user = get_user_by_telegram_id(
        telegram_id
    )

    user_id = user.get("id")

    if user_id is None:
        raise RuntimeError(
            "User ID tidak dijumpai."
        )

    first_day = today.replace(
        day=1
    )

    response = (
        supabase.table("receipts")
        .select(
            "id,total,category,receipt_date"
        )
        .eq("user_id", user_id)
        .gte(
            "receipt_date",
            first_day.isoformat(),
        )
        .lte(
            "receipt_date",
            today.isoformat(),
        )
        .execute()
    )

    receipts = response.data or []

    total_spending = 0.0

    category_data: defaultdict[
        str,
        dict[str, Any],
    ] = defaultdict(
        lambda: {
            "total": 0.0,
            "receipt_count": 0,
        }
    )

    for receipt in receipts:
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

        category = (
            receipt.get("category")
            or "Lain-lain"
        )

        total_spending += total

        category_data[category][
            "total"
        ] += total

        category_data[category][
            "receipt_count"
        ] += 1

    categories = []

    for category, data in category_data.items():
        categories.append(
            {
                "category": category,
                "total": data["total"],
                "receipt_count": data[
                    "receipt_count"
                ],
            }
        )

    categories.sort(
        key=lambda item: item["total"],
        reverse=True,
    )

    return {
        "month": today.month,
        "year": today.year,
        "total_spending": total_spending,
        "receipt_count": len(receipts),
        "categories": categories,
    }