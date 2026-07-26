from pathlib import Path

from pydantic import BaseModel


class PendingReceipt(BaseModel):
    """Data resit yang menunggu pengesahan pengguna."""

    telegram_id: int
    merchant: str
    receipt_date: str
    total: float
    category: str
    image_path: str
    chat_id: int
    message_id: int | None = None


pending_receipts: dict[int, PendingReceipt] = {}


def save_pending_receipt(
    receipt: PendingReceipt,
) -> None:
    """Simpan atau gantikan resit pending pengguna."""

    previous_receipt = pending_receipts.get(
        receipt.telegram_id
    )

    if previous_receipt is not None:
        previous_image = Path(
            previous_receipt.image_path
        )

        if (
            previous_image.exists()
            and previous_image
            != Path(receipt.image_path)
        ):
            previous_image.unlink()

    pending_receipts[receipt.telegram_id] = receipt


def get_pending_receipt(
    telegram_id: int,
) -> PendingReceipt | None:
    """Ambil resit pending berdasarkan Telegram ID."""

    return pending_receipts.get(telegram_id)


def update_pending_message_id(
    telegram_id: int,
    message_id: int,
) -> None:
    """Simpan ID mesej preview Telegram."""

    receipt = pending_receipts.get(telegram_id)

    if receipt is None:
        return

    receipt.message_id = message_id


def delete_pending_receipt(
    telegram_id: int,
    delete_image: bool = False,
) -> PendingReceipt | None:
    """Padam resit pending dan gambar jika diminta."""

    receipt = pending_receipts.pop(
        telegram_id,
        None,
    )

    if receipt is None:
        return None

    if delete_image:
        image_path = Path(receipt.image_path)

        if image_path.exists():
            image_path.unlink()

    return receipt