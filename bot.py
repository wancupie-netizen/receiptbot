import asyncio
import logging
from pathlib import Path
from uuid import uuid4

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

from ai import ReceiptData, extract_receipt
from database import get_or_create_user
from pending import (
    PendingReceipt,
    delete_pending_receipt,
    get_pending_receipt,
    save_pending_receipt,
    update_pending_message_id,
)


logger = logging.getLogger(__name__)

TEMP_RECEIPT_FOLDER = Path("temp_receipts")
TEMP_RECEIPT_FOLDER.mkdir(exist_ok=True)

CALLBACK_CONFIRM = "receipt_confirm"
CALLBACK_CANCEL = "receipt_cancel"


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
                "ReceiptBot sedang aktif.\n"
                "Hantar gambar resit untuk mula."
            )

        await update.message.reply_text(message)

    except Exception as error:
        logger.exception(
            "Gagal mendapatkan atau mencipta "
            "pengguna: %s",
            error,
        )

        await update.message.reply_text(
            "Bot aktif, tetapi akaun anda gagal "
            "disimpan.\n"
            "Sila cuba semula."
        )


def build_confirmation_keyboard(
) -> InlineKeyboardMarkup:
    """Bina butang pengesahan resit."""

    keyboard = [
        [
            InlineKeyboardButton(
                text="✅ Sahkan",
                callback_data=CALLBACK_CONFIRM,
            ),
            InlineKeyboardButton(
                text="❌ Batal",
                callback_data=CALLBACK_CANCEL,
            ),
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def format_receipt_preview(
    receipt: ReceiptData,
) -> str:
    """Sediakan teks preview resit."""

    return (
        "🧾 Preview Resit\n\n"
        "──────────────\n"
        f"🏪 Kedai\n{receipt.merchant}\n\n"
        f"📅 Tarikh\n{receipt.receipt_date}\n\n"
        f"💰 Jumlah\nRM{receipt.total:,.2f}\n\n"
        f"📂 Kategori\n{receipt.category}\n"
        "──────────────\n\n"
        "Adakah maklumat ini betul?"
    )


def format_confirmed_preview(
    receipt: PendingReceipt,
) -> str:
    """Sediakan mesej selepas pengguna mengesahkan."""

    return (
        "✅ Resit telah disahkan\n\n"
        "──────────────\n"
        f"🏪 Kedai\n{receipt.merchant}\n\n"
        f"📅 Tarikh\n{receipt.receipt_date}\n\n"
        f"💰 Jumlah\nRM{receipt.total:,.2f}\n\n"
        f"📂 Kategori\n{receipt.category}\n"
        "──────────────\n\n"
        "Data belum disimpan ke Supabase.\n"
        "Proses simpan akan ditambah dalam "
        "langkah seterusnya."
    )


async def receive_receipt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Muat turun, baca dan sediakan preview resit."""

    if update.message is None:
        return

    if not update.message.photo:
        return

    telegram_user = update.effective_user
    chat = update.effective_chat

    if telegram_user is None or chat is None:
        await update.message.reply_text(
            "Maklumat pengguna tidak dapat dibaca."
        )
        return

    status_message = await update.message.reply_text(
        "Gambar resit diterima ✅\n\n"
        "ReceiptBot sedang membaca resit..."
    )

    file_path: Path | None = None

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
            if file_path.exists():
                file_path.unlink()

            await status_message.edit_text(
                "Gambar ini tidak kelihatan "
                "seperti resit.\n\n"
                "Sila hantar gambar resit yang jelas."
            )
            return

        pending_receipt = PendingReceipt(
            telegram_id=telegram_user.id,
            merchant=receipt_data.merchant,
            receipt_date=receipt_data.receipt_date,
            total=receipt_data.total,
            category=receipt_data.category,
            image_path=str(file_path),
            chat_id=chat.id,
            message_id=status_message.message_id,
        )

        save_pending_receipt(pending_receipt)

        preview = format_receipt_preview(
            receipt_data
        )

        await status_message.edit_text(
            text=preview,
            reply_markup=build_confirmation_keyboard(),
        )

        update_pending_message_id(
            telegram_id=telegram_user.id,
            message_id=status_message.message_id,
        )

        logger.info(
            "Resit pending disimpan untuk "
            "Telegram ID: %s",
            telegram_user.id,
        )

    except Exception as error:
        logger.exception(
            "Gagal memproses gambar resit: %s",
            error,
        )

        if file_path is not None and file_path.exists():
            file_path.unlink()

        await status_message.edit_text(
            "ReceiptBot gagal membaca resit ini.\n\n"
            "Pastikan gambar jelas dan cuba semula."
        )


async def handle_receipt_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Urus tindakan Sahkan atau Batal."""

    query = update.callback_query

    if query is None:
        return

    await query.answer()

    telegram_user = update.effective_user

    if telegram_user is None:
        await query.edit_message_text(
            "Maklumat pengguna tidak dapat dibaca."
        )
        return

    receipt = get_pending_receipt(
        telegram_user.id
    )

    if receipt is None:
        await query.edit_message_text(
            "Resit ini sudah tamat atau "
            "tidak lagi tersedia.\n\n"
            "Sila hantar semula gambar resit."
        )
        return

    if query.data == CALLBACK_CANCEL:
        delete_pending_receipt(
            telegram_id=telegram_user.id,
            delete_image=True,
        )

        logger.info(
            "Resit pending dibatalkan untuk "
            "Telegram ID: %s",
            telegram_user.id,
        )

        await query.edit_message_text(
            "❌ Resit dibatalkan.\n\n"
            "Gambar dan data sementara telah dipadam."
        )
        return

    if query.data == CALLBACK_CONFIRM:
        logger.info(
            "Resit pending disahkan untuk "
            "Telegram ID: %s",
            telegram_user.id,
        )

        await query.edit_message_text(
            format_confirmed_preview(receipt)
        )
        return

    await query.edit_message_text(
        "Tindakan tidak dikenali."
    )