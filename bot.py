import asyncio
import logging
from datetime import datetime
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
    update_pending_receipt,
)


logger = logging.getLogger(__name__)

TEMP_RECEIPT_FOLDER = Path("temp_receipts")
TEMP_RECEIPT_FOLDER.mkdir(exist_ok=True)

CALLBACK_CONFIRM = "receipt_confirm"
CALLBACK_EDIT = "receipt_edit"
CALLBACK_CANCEL = "receipt_cancel"

EDIT_STEP_MERCHANT = "merchant"
EDIT_STEP_DATE = "receipt_date"
EDIT_STEP_TOTAL = "total"
EDIT_STEP_CATEGORY = "category"

ALLOWED_CATEGORIES = [
    "Bahan Mentah",
    "Packaging",
    "Peralatan",
    "Penghantaran",
    "Pemasaran",
    "Utiliti",
    "Sewa",
    "Lain-lain",
]


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

        await update.message.reply_text(
            message
        )

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
    """Bina butang tindakan resit."""

    keyboard = [
        [
            InlineKeyboardButton(
                text="✅ Sahkan",
                callback_data=CALLBACK_CONFIRM,
            ),
            InlineKeyboardButton(
                text="✏️ Betulkan",
                callback_data=CALLBACK_EDIT,
            ),
        ],
        [
            InlineKeyboardButton(
                text="❌ Batal",
                callback_data=CALLBACK_CANCEL,
            ),
        ],
    ]

    return InlineKeyboardMarkup(
        keyboard
    )


def format_receipt_preview(
    receipt: ReceiptData | PendingReceipt,
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
        "Maklumat ini belum disimpan."
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

    context.user_data.pop(
        "edit_step",
        None,
    )

    context.user_data.pop(
        "edit_data",
        None,
    )

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

        save_pending_receipt(
            pending_receipt
        )

        await status_message.edit_text(
            text=format_receipt_preview(
                receipt_data
            ),
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

        if (
            file_path is not None
            and file_path.exists()
        ):
            file_path.unlink()

        await status_message.edit_text(
            "ReceiptBot gagal membaca resit ini.\n\n"
            "Pastikan gambar jelas dan cuba semula."
        )


async def handle_receipt_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Urus tindakan Sahkan, Betulkan atau Batal."""

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

        context.user_data.pop(
            "edit_step",
            None,
        )

        context.user_data.pop(
            "edit_data",
            None,
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

    if query.data == CALLBACK_EDIT:
        context.user_data["edit_step"] = (
            EDIT_STEP_MERCHANT
        )

        context.user_data["edit_data"] = {
            "merchant": receipt.merchant,
            "receipt_date": receipt.receipt_date,
            "total": receipt.total,
            "category": receipt.category,
        }

        await query.edit_message_text(
            "✏️ Betulkan maklumat resit\n\n"
            "Masukkan nama kedai yang betul.\n\n"
            f"Nama sekarang:\n{receipt.merchant}"
        )
        return

    if query.data == CALLBACK_CONFIRM:
        logger.info(
            "Resit pending disahkan untuk "
            "Telegram ID: %s",
            telegram_user.id,
        )

        await query.edit_message_text(
            format_confirmed_preview(
                receipt
            )
        )
        return

    await query.edit_message_text(
        "Tindakan tidak dikenali."
    )


async def handle_text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Urus input pembetulan resit."""

    if (
        update.message is None
        or update.message.text is None
    ):
        return

    telegram_user = update.effective_user

    if telegram_user is None:
        return

    edit_step = context.user_data.get(
        "edit_step"
    )

    edit_data = context.user_data.get(
        "edit_data"
    )

    if not edit_step or not edit_data:
        await update.message.reply_text(
            "Hantar gambar resit untuk mula."
        )
        return

    user_input = update.message.text.strip()

    if edit_step == EDIT_STEP_MERCHANT:
        if not user_input:
            await update.message.reply_text(
                "Nama kedai tidak boleh kosong."
            )
            return

        edit_data["merchant"] = user_input
        context.user_data["edit_step"] = (
            EDIT_STEP_DATE
        )

        await update.message.reply_text(
            "Masukkan tarikh resit.\n\n"
            "Format: YYYY-MM-DD\n"
            "Contoh: 2026-07-25"
        )
        return

    if edit_step == EDIT_STEP_DATE:
        try:
            datetime.strptime(
                user_input,
                "%Y-%m-%d",
            )
        except ValueError:
            await update.message.reply_text(
                "Format tarikh tidak betul.\n\n"
                "Gunakan format YYYY-MM-DD.\n"
                "Contoh: 2026-07-25"
            )
            return

        edit_data["receipt_date"] = user_input
        context.user_data["edit_step"] = (
            EDIT_STEP_TOTAL
        )

        await update.message.reply_text(
            "Masukkan jumlah akhir resit.\n\n"
            "Contoh: 39.80"
        )
        return

    if edit_step == EDIT_STEP_TOTAL:
        try:
            total = float(
                user_input.replace(
                    "RM",
                    "",
                )
                .replace(
                    ",",
                    "",
                )
                .strip()
            )
        except ValueError:
            await update.message.reply_text(
                "Jumlah tidak sah.\n\n"
                "Masukkan nombor sahaja.\n"
                "Contoh: 39.80"
            )
            return

        if total < 0:
            await update.message.reply_text(
                "Jumlah tidak boleh negatif."
            )
            return

        edit_data["total"] = total
        context.user_data["edit_step"] = (
            EDIT_STEP_CATEGORY
        )

        categories = "\n".join(
            f"- {category}"
            for category in ALLOWED_CATEGORIES
        )

        await update.message.reply_text(
            "Masukkan kategori yang betul.\n\n"
            f"{categories}"
        )
        return

    if edit_step == EDIT_STEP_CATEGORY:
        matched_category = next(
            (
                category
                for category in ALLOWED_CATEGORIES
                if category.lower()
                == user_input.lower()
            ),
            None,
        )

        if matched_category is None:
            categories = "\n".join(
                f"- {category}"
                for category in ALLOWED_CATEGORIES
            )

            await update.message.reply_text(
                "Kategori tidak dikenali.\n\n"
                "Pilih salah satu:\n"
                f"{categories}"
            )
            return

        edit_data["category"] = matched_category

        updated_receipt = update_pending_receipt(
            telegram_id=telegram_user.id,
            merchant=edit_data["merchant"],
            receipt_date=edit_data["receipt_date"],
            total=edit_data["total"],
            category=edit_data["category"],
        )

        context.user_data.pop(
            "edit_step",
            None,
        )

        context.user_data.pop(
            "edit_data",
            None,
        )

        if updated_receipt is None:
            await update.message.reply_text(
                "Resit sementara tidak dijumpai.\n\n"
                "Sila hantar semula gambar resit."
            )
            return

        await update.message.reply_text(
            text=format_receipt_preview(
                updated_receipt
            ),
            reply_markup=build_confirmation_keyboard(),
        )