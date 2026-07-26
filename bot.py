import logging
from pathlib import Path
from uuid import uuid4

from telegram import Update
from telegram.ext import ContextTypes

from database import get_or_create_user


logger = logging.getLogger(__name__)

TEMP_RECEIPT_FOLDER = Path("temp_receipts")
TEMP_RECEIPT_FOLDER.mkdir(exist_ok=True)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Daftar pengguna Telegram atau sambut pengguna sedia ada."""

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
        _, is_new_user = get_or_create_user(
            telegram_id=telegram_user.id,
            name=name,
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


async def receive_receipt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Muat turun gambar resit dari Telegram."""

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

    await update.message.reply_text(
        "Gambar resit diterima ✅\n\n"
        "ReceiptBot sedang memuat turun gambar."
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
            "Gambar resit disimpan: %s",
            file_path,
        )

        await update.message.reply_text(
            "Gambar resit berjaya disimpan sementara ✅"
        )

    except Exception as error:
        logger.exception(
            "Gagal memuat turun gambar resit: %s",
            error,
        )

        await update.message.reply_text(
            "Gambar resit gagal dimuat turun.\n"
            "Sila cuba semula."
        )