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

CALLBACK_EDIT_MERCHANT = "edit_merchant"
CALLBACK_EDIT_DATE = "edit_date"
CALLBACK_EDIT_TOTAL = "edit_total"
CALLBACK_EDIT_CATEGORY = "edit_category"
CALLBACK_EDIT_BACK = "edit_back"

CALLBACK_CATEGORY_PREFIX = "category:"


EDIT_FIELD_MERCHANT = "merchant"
EDIT_FIELD_DATE = "receipt_date"
EDIT_FIELD_TOTAL = "total"


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


def build_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Bina butang tindakan utama resit."""

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

    return InlineKeyboardMarkup(keyboard)


def build_edit_field_keyboard() -> InlineKeyboardMarkup:
    """Bina pilihan medan yang mahu dibetulkan."""

    keyboard = [
        [
            InlineKeyboardButton(
                text="🏪 Kedai",
                callback_data=CALLBACK_EDIT_MERCHANT,
            ),
            InlineKeyboardButton(
                text="📅 Tarikh",
                callback_data=CALLBACK_EDIT_DATE,
            ),
        ],
        [
            InlineKeyboardButton(
                text="💰 Jumlah",
                callback_data=CALLBACK_EDIT_TOTAL,
            ),
            InlineKeyboardButton(
                text="📂 Kategori",
                callback_data=CALLBACK_EDIT_CATEGORY,
            ),
        ],
        [
            InlineKeyboardButton(
                text="↩️ Kembali",
                callback_data=CALLBACK_EDIT_BACK,
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def build_category_keyboard() -> InlineKeyboardMarkup:
    """Bina butang pilihan kategori."""

    keyboard = [
        [
            InlineKeyboardButton(
                text="Bahan Mentah",
                callback_data=(
                    f"{CALLBACK_CATEGORY_PREFIX}Bahan Mentah"
                ),
            ),
            InlineKeyboardButton(
                text="Packaging",
                callback_data=(
                    f"{CALLBACK_CATEGORY_PREFIX}Packaging"
                ),
            ),
        ],
        [
            InlineKeyboardButton(
                text="Peralatan",
                callback_data=(
                    f"{CALLBACK_CATEGORY_PREFIX}Peralatan"
                ),
            ),
            InlineKeyboardButton(
                text="Penghantaran",
                callback_data=(
                    f"{CALLBACK_CATEGORY_PREFIX}Penghantaran"
                ),
            ),
        ],
        [
            InlineKeyboardButton(
                text="Pemasaran",
                callback_data=(
                    f"{CALLBACK_CATEGORY_PREFIX}Pemasaran"
                ),
            ),
            InlineKeyboardButton(
                text="Utiliti",
                callback_data=(
                    f"{CALLBACK_CATEGORY_PREFIX}Utiliti"
                ),
            ),
        ],
        [
            InlineKeyboardButton(
                text="Sewa",
                callback_data=(
                    f"{CALLBACK_CATEGORY_PREFIX}Sewa"
                ),
            ),
            InlineKeyboardButton(
                text="Lain-lain",
                callback_data=(
                    f"{CALLBACK_CATEGORY_PREFIX}Lain-lain"
                ),
            ),
        ],
        [
            InlineKeyboardButton(
                text="↩️ Kembali",
                callback_data=CALLBACK_EDIT,
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


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


def clear_edit_state(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Kosongkan status pembetulan pengguna."""

    context.user_data.pop(
        "edit_field",
        None,
    )


async def show_receipt_preview(
    update: Update,
    receipt: PendingReceipt,
) -> None:
    """Paparkan preview resit melalui callback query."""

    query = update.callback_query

    if query is None:
        return

    await query.edit_message_text(
        text=format_receipt_preview(receipt),
        reply_markup=build_confirmation_keyboard(),
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

    clear_edit_state(context)

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
                "Gambar ini tidak kelihatan seperti resit.\n\n"
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

        await status_message.edit_text(
            text=format_receipt_preview(receipt_data),
            reply_markup=build_confirmation_keyboard(),
        )

        update_pending_message_id(
            telegram_id=telegram_user.id,
            message_id=status_message.message_id,
        )

        logger.info(
            "Resit pending disimpan untuk Telegram ID: %s",
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
    """Urus tindakan resit melalui inline button."""

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
        clear_edit_state(context)

        await query.edit_message_text(
            "Resit ini sudah tamat atau tidak lagi tersedia.\n\n"
            "Sila hantar semula gambar resit."
        )
        return

    callback_data = query.data or ""

    if callback_data == CALLBACK_CANCEL:
        delete_pending_receipt(
            telegram_id=telegram_user.id,
            delete_image=True,
        )

        clear_edit_state(context)

        logger.info(
            "Resit pending dibatalkan untuk Telegram ID: %s",
            telegram_user.id,
        )

        await query.edit_message_text(
            "❌ Resit dibatalkan.\n\n"
            "Gambar dan data sementara telah dipadam."
        )
        return

    if callback_data == CALLBACK_CONFIRM:
        clear_edit_state(context)

        logger.info(
            "Resit pending disahkan untuk Telegram ID: %s",
            telegram_user.id,
        )

        await query.edit_message_text(
            format_confirmed_preview(receipt)
        )
        return

    if callback_data == CALLBACK_EDIT:
        clear_edit_state(context)

        await query.edit_message_text(
            text=(
                "✏️ Pilih maklumat yang mahu dibetulkan.\n\n"
                f"🏪 Kedai: {receipt.merchant}\n"
                f"📅 Tarikh: {receipt.receipt_date}\n"
                f"💰 Jumlah: RM{receipt.total:,.2f}\n"
                f"📂 Kategori: {receipt.category}"
            ),
            reply_markup=build_edit_field_keyboard(),
        )
        return

    if callback_data == CALLBACK_EDIT_BACK:
        clear_edit_state(context)

        await show_receipt_preview(
            update,
            receipt,
        )
        return

    if callback_data == CALLBACK_EDIT_MERCHANT:
        context.user_data["edit_field"] = (
            EDIT_FIELD_MERCHANT
        )

        await query.edit_message_text(
            "🏪 Betulkan nama kedai\n\n"
            f"Nama sekarang:\n{receipt.merchant}\n\n"
            "Taip nama kedai yang betul."
        )
        return

    if callback_data == CALLBACK_EDIT_DATE:
        context.user_data["edit_field"] = (
            EDIT_FIELD_DATE
        )

        await query.edit_message_text(
            "📅 Betulkan tarikh resit\n\n"
            f"Tarikh sekarang:\n{receipt.receipt_date}\n\n"
            "Taip tarikh yang betul menggunakan format:\n"
            "YYYY-MM-DD\n\n"
            "Contoh: 2026-07-25"
        )
        return

    if callback_data == CALLBACK_EDIT_TOTAL:
        context.user_data["edit_field"] = (
            EDIT_FIELD_TOTAL
        )

        await query.edit_message_text(
            "💰 Betulkan jumlah resit\n\n"
            f"Jumlah sekarang:\nRM{receipt.total:,.2f}\n\n"
            "Taip jumlah yang betul.\n"
            "Contoh: 39.80"
        )
        return

    if callback_data == CALLBACK_EDIT_CATEGORY:
        clear_edit_state(context)

        await query.edit_message_text(
            text=(
                "📂 Pilih kategori yang betul.\n\n"
                f"Kategori sekarang:\n{receipt.category}"
            ),
            reply_markup=build_category_keyboard(),
        )
        return

    if callback_data.startswith(
        CALLBACK_CATEGORY_PREFIX
    ):
        selected_category = callback_data.removeprefix(
            CALLBACK_CATEGORY_PREFIX
        )

        if selected_category not in ALLOWED_CATEGORIES:
            await query.edit_message_text(
                "Kategori tidak dikenali.\n\n"
                "Sila cuba semula."
            )
            return

        updated_receipt = update_pending_receipt(
            telegram_id=telegram_user.id,
            merchant=receipt.merchant,
            receipt_date=receipt.receipt_date,
            total=receipt.total,
            category=selected_category,
        )

        clear_edit_state(context)

        if updated_receipt is None:
            await query.edit_message_text(
                "Resit sementara tidak dijumpai.\n\n"
                "Sila hantar semula gambar resit."
            )
            return

        logger.info(
            "Kategori resit dikemas kini untuk Telegram ID: %s",
            telegram_user.id,
        )

        await query.edit_message_text(
            text=format_receipt_preview(
                updated_receipt
            ),
            reply_markup=build_confirmation_keyboard(),
        )
        return

    await query.edit_message_text(
        "Tindakan tidak dikenali."
    )


async def handle_text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Urus nilai baharu untuk satu medan resit."""

    if (
        update.message is None
        or update.message.text is None
    ):
        return

    telegram_user = update.effective_user

    if telegram_user is None:
        return

    edit_field = context.user_data.get(
        "edit_field"
    )

    if not edit_field:
        await update.message.reply_text(
            "Hantar gambar resit untuk mula."
        )
        return

    receipt = get_pending_receipt(
        telegram_user.id
    )

    if receipt is None:
        clear_edit_state(context)

        await update.message.reply_text(
            "Resit sementara tidak dijumpai.\n\n"
            "Sila hantar semula gambar resit."
        )
        return

    user_input = update.message.text.strip()

    merchant = receipt.merchant
    receipt_date = receipt.receipt_date
    total = receipt.total
    category = receipt.category

    if edit_field == EDIT_FIELD_MERCHANT:
        if not user_input:
            await update.message.reply_text(
                "Nama kedai tidak boleh kosong.\n\n"
                "Taip nama kedai yang betul."
            )
            return

        merchant = user_input

    elif edit_field == EDIT_FIELD_DATE:
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

        receipt_date = user_input

    elif edit_field == EDIT_FIELD_TOTAL:
        cleaned_total = (
            user_input
            .upper()
            .replace("RM", "")
            .replace(",", "")
            .strip()
        )

        try:
            parsed_total = float(cleaned_total)
        except ValueError:
            await update.message.reply_text(
                "Jumlah tidak sah.\n\n"
                "Masukkan nombor sahaja.\n"
                "Contoh: 39.80"
            )
            return

        if parsed_total < 0:
            await update.message.reply_text(
                "Jumlah tidak boleh negatif."
            )
            return

        total = parsed_total

    else:
        clear_edit_state(context)

        await update.message.reply_text(
            "Sesi pembetulan tidak dikenali.\n\n"
            "Sila tekan Betulkan semula."
        )
        return

    updated_receipt = update_pending_receipt(
        telegram_id=telegram_user.id,
        merchant=merchant,
        receipt_date=receipt_date,
        total=total,
        category=category,
    )

    clear_edit_state(context)

    if updated_receipt is None:
        await update.message.reply_text(
            "Resit sementara tidak dijumpai.\n\n"
            "Sila hantar semula gambar resit."
        )
        return

    logger.info(
        "Maklumat resit dikemas kini untuk Telegram ID: %s",
        telegram_user.id,
    )

    await update.message.reply_text(
        text=format_receipt_preview(
            updated_receipt
        ),
        reply_markup=build_confirmation_keyboard(),
    )