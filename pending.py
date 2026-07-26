from pathlib import Path
from typing import Any


pending_receipts: dict[int, dict[str, Any]] = {}


def save_pending_receipt(
    telegram_id: int,
    merchant: str,
    receipt_date: str,
    total: float,
    category: str,
    image_path: Path,
) -> None:
    """Simpan resit sementara berdasarkan Telegram ID."""

    pending_receipts[telegram_id] = {
        "merchant": merchant,
        "receipt_date": receipt_date,
        "total": total,
        "category": category,
        "image_path": str(image_path),
    }


def get_pending_receipt(
    telegram_id: int,
) -> dict[str, Any] | None:
    """Ambil resit sementara pengguna."""

    return pending_receipts.get(telegram_id)


def delete_pending_receipt(
    telegram_id: int,
) -> None:
    """Padam resit sementara pengguna."""

    pending_receipts.pop(
        telegram_id,
        None,
    )