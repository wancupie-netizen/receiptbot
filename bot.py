import asyncio
import logging
from pathlib import Path
from uuid import uuid4

from telegram import Update
from telegram.ext import ContextTypes

from ai import ReceiptData, extract_receipt
from database import get_or_create_user
from pending import save_pending_receipt


logger = logging.getLogger(__name__)

TEMP_RECEIPT_FOLDER = Path("temp_receipts")
TEMP_RECEIPT_FOLDER.mkdir(exist_ok=True)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Daftar atau sambut pengguna Telegram."""

    if update.message is None:
        return

    telegram_user = update.effective_user

    if telegram_user is None:
        await update.message.reply_text(
            "Maklumat pengguna tidak dapat dibaca."
        )
        return

    name = telegram_user.first_name or "Pengguna"

    try:
        _, is_new_user = await asyncio.to_thread(
            get_or_create_user,
            telegram_user.id,
            name,
        )

        if is_new_user:
            message = (
                f"Selamat datang, {name} 👋\n\n"
                "Akaun ReceiptBot anda sudah disediakan.\n"
                "Anda boleh hantar gambar resit di sini."
            )
        else:
            message = (
                f"Selamat kembali, {name} 👋\n\n"
                "ReceiptBot sedang aktif."
            )

        await update.message.reply_text(message)

    except Exception as error:
        logger.exception(
            "Gagal mendapatkan atau mencipta pengguna: %s",
            error,
        )

        await update.message.reply_text(
            "Bot aktif, tetapi akaun anda gagal disimpan.\n"
            "Sila cuba semula."
        )


def format_receipt_preview(
    receipt: ReceiptData,
) -> str:
    """Sediakan teks preview hasil bacaan resit."""

    return (
        "Resit berjaya dibaca ✅\n\n"
        "──────────────\n"
        f"🏪 Kedai\n{receipt.merchant}\n\n"
        f"📅 Tarikh\n{receipt.receipt_date}\n\n"
        f"💰 Jumlah\nRM{receipt.total:,.2f}\n\n"
        f"📂 Kategori\n{receipt.category}\n"
        "──────────────\n\n"
        "Data ini disimpan sementara.\n"
        "Belum dimasukkan ke rekod perbelanjaan."
    )


async def receive_receipt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Muat turun, baca dan simpan resit sementara."""

    if update.message is None:
        return

    if not update.message.photo:
        return

    telegram_user = update.effective_user

    if telegram_user is None:
        await update.message.reply_text(
            "Maklumat pengguna tidak dapat dibaca."
        )
        return

    status_message = await update.message.reply_text(
        "Gambar resit diterima ✅\n\n"
        "ReceiptBot sedang membaca resit..."
    )

    try:
        largest_photo = update.message.photo[-1]
        telegram_file = await largest_photo.get_file()

        filename = (
            f"{telegram_user.id}_"
            f"{uuid4().hex}.jpg"
        )

        file_path = TEMP_RECEIPT_FOLDER / filename

        await telegram_file.download_to_drive(
            custom_path=file_path
        )

        logger.info(
            "Gambar resit disimpan sementara: %s",
            file_path,
        )

        receipt_data = await asyncio.to_thread(
            extract_receipt,
            file_path,
        )

        if not receipt_data.is_receipt:
            await status_message.edit_text(
                "Gambar ini tidak kelihatan seperti resit.\n\n"
                "Sila hantar gambar resit yang jelas."
            )
            return

        save_pending_receipt(
            telegram_id=telegram_user.id,
            merchant=receipt_data.merchant,
            receipt_date=receipt_data.receipt_date,
            total=receipt_data.total,
            category=receipt_data.category,
            image_path=file_path,
        )

        logger.info(
            "Resit sementara disimpan untuk Telegram ID: %s",
            telegram_user.id,
        )

        preview = format_receipt_preview(
            receipt_data
        )

        await status_message.edit_text(preview)

    except Exception as error:
        logger.exception(
            "Gagal memproses gambar resit: %s",
            error,
        )

        await status_message.edit_text(
            "ReceiptBot gagal membaca resit ini.\n\n"
            "Pastikan gambar jelas dan cuba semula."
        )