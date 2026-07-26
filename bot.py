import logging

from telegram import Update
from telegram.ext import ContextTypes

from database import get_or_create_user


logger = logging.getLogger(__name__)


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
                "Nanti anda boleh hantar gambar resit di sini."
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