import mimetypes
from datetime import datetime
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


def build_receipt_storage_path(
    telegram_id: int,
    receipt_date: str,
    image_path: Path,
) -> str:
    """Bina lokasi fail yang tersusun dalam Storage."""

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