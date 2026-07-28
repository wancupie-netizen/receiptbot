import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from telegram import (
    Contact,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)

from database import (
    get_or_create_user,
    get_user_by_telegram_id,
    supabase,
)


logger = logging.getLogger(__name__)


BILLING_PHONE = 1
BILLING_EMAIL = 2
BILLING_CONFIRM = 3


CALLBACK_BILLING_CONFIRM = (
    "billing:confirm"
)

CALLBACK_BILLING_RESTART = (
    "billing:restart"
)

CALLBACK_BILLING_CANCEL = (
    "billing:cancel"
)


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+\-]+@"
    r"[A-Za-z0-9.\-]+\."
    r"[A-Za-z]{2,}$"
)


@dataclass(
    frozen=True,
    slots=True,
)
class BillingProfile:
    """Maklumat billing pengguna."""

    profile_id: str
    user_id: int
    telegram_id: int

    full_name: str
    email: str
    phone_number: str

    consent_at: datetime
    created_at: datetime
    updated_at: datetime


def parse_datetime(
    value: Any,
) -> datetime:
    """Tukar nilai Supabase kepada datetime UTC."""

    if not isinstance(
        value,
        str,
    ):
        raise RuntimeError(
            "Tarikh Billing Profile tidak sah."
        )

    normalized_value = value.replace(
        "Z",
        "+00:00",
    )

    try:
        parsed_value = datetime.fromisoformat(
            normalized_value
        )
    except ValueError as error:
        raise RuntimeError(
            "Tarikh Billing Profile tidak sah."
        ) from error

    if parsed_value.tzinfo is None:
        return parsed_value.replace(
            tzinfo=timezone.utc
        )

    return parsed_value.astimezone(
        timezone.utc
    )


def billing_profile_from_row(
    row: dict[str, Any],
) -> BillingProfile:
    """Tukar row database kepada BillingProfile."""

    profile_id = row.get("id")
    user_id = row.get("user_id")
    telegram_id = row.get("telegram_id")

    full_name = row.get("full_name")
    email = row.get("email")
    phone_number = row.get("phone_number")

    if (
        profile_id is None
        or user_id is None
        or telegram_id is None
        or full_name is None
        or email is None
        or phone_number is None
    ):
        raise RuntimeError(
            "Rekod Billing Profile tidak lengkap."
        )

    return BillingProfile(
        profile_id=str(profile_id),
        user_id=int(user_id),
        telegram_id=int(telegram_id),
        full_name=str(full_name),
        email=str(email),
        phone_number=str(phone_number),
        consent_at=parse_datetime(
            row.get("consent_at")
        ),
        created_at=parse_datetime(
            row.get("created_at")
        ),
        updated_at=parse_datetime(
            row.get("updated_at")
        ),
    )


def get_billing_profile(
    telegram_id: int,
) -> BillingProfile | None:
    """Dapatkan Billing Profile pengguna."""

    response = (
        supabase.table("billing_profiles")
        .select("*")
        .eq(
            "telegram_id",
            telegram_id,
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return billing_profile_from_row(
        response.data[0]
    )


def billing_profile_is_complete(
    telegram_id: int,
) -> bool:
    """Semak sama ada Billing Profile lengkap."""

    profile = get_billing_profile(
        telegram_id
    )

    if profile is None:
        return False

    return bool(
        profile.full_name.strip()
        and profile.email.strip()
        and profile.phone_number.strip()
    )


def normalize_email(
    raw_email: str,
) -> str:
    """Bersihkan dan sahkan alamat email."""

    normalized_email = (
        raw_email.strip().lower()
    )

    if len(normalized_email) > 254:
        raise ValueError(
            "Alamat email terlalu panjang."
        )

    if not EMAIL_PATTERN.fullmatch(
        normalized_email
    ):
        raise ValueError(
            "Format alamat email tidak sah."
        )

    return normalized_email


def normalize_phone_number(
    raw_phone_number: str,
) -> str:
    """
    Tukar nombor Malaysia kepada format E.164.

    Contoh:
    0123456789  → +60123456789
    60123456789 → +60123456789
    """

    cleaned_number = re.sub(
        r"[^\d+]",
        "",
        raw_phone_number.strip(),
    )

    if cleaned_number.startswith(
        "00"
    ):
        cleaned_number = (
            "+"
            + cleaned_number[2:]
        )

    if cleaned_number.startswith(
        "0"
    ):
        cleaned_number = (
            "+60"
            + cleaned_number[1:]
        )

    elif cleaned_number.startswith(
        "60"
    ):
        cleaned_number = (
            "+"
            + cleaned_number
        )

    elif not cleaned_number.startswith(
        "+"
    ):
        cleaned_number = (
            "+"
            + cleaned_number
        )

    if not re.fullmatch(
        r"\+[1-9][0-9]{7,14}",
        cleaned_number,
    ):
        raise ValueError(
            "Nombor telefon tidak sah."
        )

    return cleaned_number


def save_billing_profile(
    telegram_id: int,
    full_name: str,
    email: str,
    phone_number: str,
) -> BillingProfile:
    """Cipta atau kemas kini Billing Profile."""

    user = get_user_by_telegram_id(
        telegram_id
    )

    user_id = user.get("id")

    if user_id is None:
        raise RuntimeError(
            "User ID tidak dijumpai."
        )

    normalized_name = (
        full_name.strip()
    )

    if len(normalized_name) < 2:
        raise ValueError(
            "Nama pengguna tidak sah."
        )

    normalized_email = normalize_email(
        email
    )

    normalized_phone = normalize_phone_number(
        phone_number
    )

    consent_at = datetime.now(
        timezone.utc
    )

    existing_profile = get_billing_profile(
        telegram_id
    )

    profile_data = {
        "user_id": int(user_id),
        "telegram_id": telegram_id,
        "full_name": normalized_name,
        "email": normalized_email,
        "phone_number": normalized_phone,
        "consent_at": (
            consent_at.isoformat()
        ),
        "metadata": {
            "source": "telegram",
            "consent_version": "v1",
        },
    }

    if existing_profile is None:
        response = (
            supabase.table("billing_profiles")
            .insert(
                profile_data
            )
            .execute()
        )

    else:
        response = (
            supabase.table("billing_profiles")
            .update(
                profile_data
            )
            .eq(
                "telegram_id",
                telegram_id,
            )
            .execute()
        )

    if not response.data:
        raise RuntimeError(
            "Billing Profile gagal disimpan."
        )

    return billing_profile_from_row(
        response.data[0]
    )


def get_phone_keyboard() -> ReplyKeyboardMarkup:
    """Bina butang perkongsian nombor telefon."""

    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    text="📱 Kongsi Nombor Telefon",
                    request_contact=True,
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder=(
            "Tekan butang untuk kongsi nombor"
        ),
    )


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Bina butang pengesahan Billing Profile."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="✅ Sahkan & Simpan",
                    callback_data=(
                        CALLBACK_BILLING_CONFIRM
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Isi Semula",
                    callback_data=(
                        CALLBACK_BILLING_RESTART
                    ),
                ),
                InlineKeyboardButton(
                    text="❌ Batal",
                    callback_data=(
                        CALLBACK_BILLING_CANCEL
                    ),
                ),
            ],
        ]
    )


def format_existing_profile(
    profile: BillingProfile,
) -> str:
    """Sediakan paparan profil sedia ada."""

    return (
        "💳 Billing Profile\n\n"
        "Maklumat semasa anda:\n\n"
        "Nama\n"
        f"{profile.full_name}\n\n"
        "Email\n"
        f"{profile.email}\n\n"
        "Nombor Telefon\n"
        f"{profile.phone_number}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Untuk mengemas kini maklumat, "
        "kongsi nombor telefon anda sekali lagi."
    )


def format_profile_preview(
    full_name: str,
    email: str,
    phone_number: str,
) -> str:
    """Sediakan preview sebelum disimpan."""

    return (
        "💳 Semak Billing Profile\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Nama\n"
        f"{full_name}\n\n"
        "Email\n"
        f"{email}\n\n"
        "Nombor Telefon\n"
        f"{phone_number}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Dengan menekan Sahkan, anda bersetuju "
        "maklumat ini digunakan bagi urusan "
        "pembayaran dan langganan ReceiptBot."
    )


def clear_billing_draft(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Padam draf Billing Profile daripada memori."""

    context.user_data.pop(
        "billing_phone_number",
        None,
    )

    context.user_data.pop(
        "billing_email",
        None,
    )

    context.user_data.pop(
        "billing_full_name",
        None,
    )


async def billing_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Mulakan flow Billing Profile."""

    if update.message is None:
        return ConversationHandler.END

    telegram_user = update.effective_user

    if telegram_user is None:
        await update.message.reply_text(
            "Maklumat pengguna tidak dapat dibaca."
        )
        return ConversationHandler.END

    clear_billing_draft(
        context
    )

    full_name = (
        telegram_user.full_name
        or telegram_user.first_name
        or "Pengguna ReceiptBot"
    )

    try:
        await asyncio.to_thread(
            get_or_create_user,
            telegram_user.id,
            full_name,
        )

        existing_profile = await asyncio.to_thread(
            get_billing_profile,
            telegram_user.id,
        )

    except Exception as error:
        logger.exception(
            "Billing Profile gagal dibaca. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await update.message.reply_text(
            "Billing Profile gagal dibuka.\n\n"
            "Sila cuba semula."
        )

        return ConversationHandler.END

    context.user_data[
        "billing_full_name"
    ] = full_name

    if existing_profile is None:
        message = (
            "💳 Billing Profile\n\n"
            "Maklumat ini diperlukan sebelum "
            "ReceiptBot boleh menghasilkan "
            "pautan pembayaran.\n\n"
            "Tekan butang di bawah untuk berkongsi "
            "nombor telefon Telegram anda."
        )

    else:
        message = format_existing_profile(
            existing_profile
        )

    await update.message.reply_text(
        message,
        reply_markup=get_phone_keyboard(),
    )

    return BILLING_PHONE


async def receive_billing_contact(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Terima nombor telefon daripada Telegram."""

    if update.message is None:
        return BILLING_PHONE

    telegram_user = update.effective_user
    contact: Contact | None = (
        update.message.contact
    )

    if (
        telegram_user is None
        or contact is None
    ):
        await update.message.reply_text(
            "Tekan butang Kongsi Nombor Telefon "
            "untuk meneruskan.",
            reply_markup=get_phone_keyboard(),
        )
        return BILLING_PHONE

    if (
        contact.user_id is not None
        and contact.user_id
        != telegram_user.id
    ):
        await update.message.reply_text(
            "Sila kongsi nombor telefon milik "
            "akaun Telegram anda sendiri.",
            reply_markup=get_phone_keyboard(),
        )
        return BILLING_PHONE

    try:
        phone_number = normalize_phone_number(
            contact.phone_number
        )

    except ValueError as error:
        await update.message.reply_text(
            f"{error}\n\n"
            "Sila cuba kongsi nombor sekali lagi.",
            reply_markup=get_phone_keyboard(),
        )
        return BILLING_PHONE

    context.user_data[
        "billing_phone_number"
    ] = phone_number

    await update.message.reply_text(
        "📧 Masukkan alamat email anda.\n\n"
        "Contoh:\n"
        "nama@email.com",
        reply_markup=ReplyKeyboardRemove(),
    )

    return BILLING_EMAIL


async def receive_billing_email(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Terima dan sahkan alamat email."""

    if (
        update.message is None
        or update.message.text is None
    ):
        return BILLING_EMAIL

    try:
        email = normalize_email(
            update.message.text
        )

    except ValueError as error:
        await update.message.reply_text(
            f"{error}\n\n"
            "Masukkan email yang sah.\n"
            "Contoh: nama@email.com"
        )
        return BILLING_EMAIL

    context.user_data[
        "billing_email"
    ] = email

    full_name = str(
        context.user_data.get(
            "billing_full_name",
            "Pengguna ReceiptBot",
        )
    )

    phone_number = str(
        context.user_data.get(
            "billing_phone_number",
            "",
        )
    )

    await update.message.reply_text(
        format_profile_preview(
            full_name=full_name,
            email=email,
            phone_number=phone_number,
        ),
        reply_markup=get_confirmation_keyboard(),
    )

    return BILLING_CONFIRM


async def handle_billing_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Proses butang pengesahan Billing Profile."""

    query = update.callback_query

    if query is None:
        return BILLING_CONFIRM

    await query.answer()

    telegram_user = update.effective_user

    if telegram_user is None:
        await query.edit_message_text(
            "Maklumat pengguna tidak dapat dibaca."
        )
        return ConversationHandler.END

    callback_data = query.data or ""

    if callback_data == CALLBACK_BILLING_CANCEL:
        clear_billing_draft(
            context
        )

        await query.edit_message_text(
            "Pengisian Billing Profile dibatalkan."
        )

        return ConversationHandler.END

    if callback_data == CALLBACK_BILLING_RESTART:
        clear_billing_draft(
            context
        )

        full_name = (
            telegram_user.full_name
            or telegram_user.first_name
            or "Pengguna ReceiptBot"
        )

        context.user_data[
            "billing_full_name"
        ] = full_name

        await query.edit_message_text(
            "Sila kongsi nombor telefon anda "
            "menggunakan butang yang dihantar."
        )

        if query.message is not None:
            await query.message.reply_text(
                "📱 Kongsi nombor telefon anda.",
                reply_markup=get_phone_keyboard(),
            )

        return BILLING_PHONE

    if callback_data != CALLBACK_BILLING_CONFIRM:
        await query.answer(
            "Pilihan tidak dikenali.",
            show_alert=True,
        )
        return BILLING_CONFIRM

    full_name = str(
        context.user_data.get(
            "billing_full_name",
            "",
        )
    )

    email = str(
        context.user_data.get(
            "billing_email",
            "",
        )
    )

    phone_number = str(
        context.user_data.get(
            "billing_phone_number",
            "",
        )
    )

    if (
        not full_name
        or not email
        or not phone_number
    ):
        await query.edit_message_text(
            "Maklumat Billing Profile tidak lengkap.\n\n"
            "Gunakan /billing untuk cuba semula."
        )

        clear_billing_draft(
            context
        )

        return ConversationHandler.END

    await query.edit_message_text(
        "⏳ Menyimpan Billing Profile..."
    )

    try:
        profile = await asyncio.to_thread(
            save_billing_profile,
            telegram_user.id,
            full_name,
            email,
            phone_number,
        )

    except Exception as error:
        logger.exception(
            "Billing Profile gagal disimpan. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await query.edit_message_text(
            "Billing Profile gagal disimpan.\n\n"
            "Sila gunakan /billing untuk cuba semula."
        )

        clear_billing_draft(
            context
        )

        return ConversationHandler.END

    clear_billing_draft(
        context
    )

    await query.edit_message_text(
        "✅ Billing Profile Berjaya Disimpan\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Nama\n"
        f"{profile.full_name}\n\n"
        "Email\n"
        f"{profile.email}\n\n"
        "Nombor Telefon\n"
        f"{profile.phone_number}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Maklumat ini akan digunakan untuk "
        "urusan pembayaran ReceiptBot.\n\n"
        "Gunakan /upgrade untuk melihat pelan."
    )

    return ConversationHandler.END


async def cancel_billing_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Batalkan flow Billing Profile."""

    clear_billing_draft(
        context
    )

    if update.message is not None:
        await update.message.reply_text(
            "Pengisian Billing Profile dibatalkan.",
            reply_markup=ReplyKeyboardRemove(),
        )

    return ConversationHandler.END