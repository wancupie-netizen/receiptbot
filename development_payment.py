import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

from config import PAYMENT_PROVIDER
from payment_repository import (
    get_payment_by_reference,
    mark_payment_paid,
)
from payment_service import (
    PaymentProviderCode,
    PaymentServiceError,
    PaymentStatus,
)
from subscription_activation_service import (
    ActivatedSubscription,
    activate_subscription_from_payment,
)


logger = logging.getLogger(__name__)

MALAYSIA_TIMEZONE = ZoneInfo(
    "Asia/Kuching"
)

CALLBACK_DEVELOPMENT_PAYMENT_PREFIX = (
    "devpay:"
)


def build_development_payment_callback(
    payment_reference: str,
) -> str:
    """Bina callback data pembayaran ujian."""

    return (
        f"{CALLBACK_DEVELOPMENT_PAYMENT_PREFIX}"
        f"{payment_reference}"
    )


def extract_payment_reference(
    callback_data: str,
) -> str:
    """Dapatkan payment reference daripada callback."""

    if not callback_data.startswith(
        CALLBACK_DEVELOPMENT_PAYMENT_PREFIX
    ):
        raise PaymentServiceError(
            "Callback pembayaran tidak sah."
        )

    payment_reference = callback_data[
        len(
            CALLBACK_DEVELOPMENT_PAYMENT_PREFIX
        ):
    ].strip()

    if not payment_reference:
        raise PaymentServiceError(
            "Payment reference tidak dijumpai."
        )

    return payment_reference


def build_development_confirmation_keyboard(
    payment_reference: str,
) -> InlineKeyboardMarkup:
    """Bina butang pengesahan pembayaran ujian."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=(
                        "🧪 Sahkan Bayaran Ujian"
                    ),
                    callback_data=(
                        build_development_payment_callback(
                            payment_reference
                        )
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text=(
                        "⬅️ Kembali ke pilihan pelan"
                    ),
                    callback_data="upgrade:BACK",
                )
            ],
        ]
    )


def format_date(
    value: datetime,
) -> str:
    """Format tarikh dalam waktu Malaysia."""

    local_value = value.astimezone(
        MALAYSIA_TIMEZONE
    )

    month_names = {
        1: "Januari",
        2: "Februari",
        3: "Mac",
        4: "April",
        5: "Mei",
        6: "Jun",
        7: "Julai",
        8: "Ogos",
        9: "September",
        10: "Oktober",
        11: "November",
        12: "Disember",
    }

    return (
        f"{local_value.day} "
        f"{month_names[local_value.month]} "
        f"{local_value.year}"
    )


def format_activation_success(
    subscription: ActivatedSubscription,
) -> str:
    """Sediakan mesej pengaktifan berjaya."""

    return (
        "✅ Pembayaran Ujian Berjaya\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Pelan Diaktifkan\n"
        f"{subscription.plan_name}\n\n"
        "Status\n"
        f"{subscription.status}\n\n"
        "Harga\n"
        f"RM{subscription.price_rm} / bulan\n\n"
        "Mula\n"
        f"{format_date(subscription.starts_at)}\n\n"
        "Tamat\n"
        f"{format_date(subscription.expires_at)}\n\n"
        "Rujukan Pembayaran\n"
        f"{subscription.payment_reference}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Akaun anda telah dikemas kini.\n"
        "Gunakan /account untuk melihat "
        "maklumat pelan terkini."
    )


def confirm_development_payment(
    payment_reference: str,
    telegram_id: int,
) -> ActivatedSubscription:
    """
    Sahkan transaksi Development terus melalui database.

    Development Gateway menyimpan transaksi dalam memori,
    tetapi Supabase ialah sumber kebenaran utama. Oleh itu,
    pengesahan ujian tidak bergantung pada memori gateway.
    """

    payment = get_payment_by_reference(
        payment_reference
    )

    if payment.telegram_id != telegram_id:
        raise PaymentServiceError(
            "Transaksi ini bukan milik anda."
        )

    if (
        payment.provider_code
        != PaymentProviderCode.DEVELOPMENT
    ):
        raise PaymentServiceError(
            "Transaksi ini bukan transaksi Development."
        )

    if payment.status == PaymentStatus.PENDING:
        payment = mark_payment_paid(
            payment_reference=payment_reference,
            provider_reference=(
                f"development_confirmed_"
                f"{payment_reference}"
            ),
            provider_payload={
                "source": (
                    "telegram_development_confirmation"
                ),
                "confirmation_type": "manual_test",
            },
        )

    elif payment.status == PaymentStatus.PAID:
        pass

    elif payment.status == PaymentStatus.REFUNDED:
        raise PaymentServiceError(
            "Pembayaran ini telah dipulangkan."
        )

    elif payment.status == PaymentStatus.CANCELLED:
        raise PaymentServiceError(
            "Pembayaran ini telah dibatalkan."
        )

    elif payment.status == PaymentStatus.FAILED:
        raise PaymentServiceError(
            "Pembayaran ini telah gagal."
        )

    else:
        raise PaymentServiceError(
            "Status pembayaran tidak boleh diproses."
        )

    return activate_subscription_from_payment(
        payment_reference
    )


async def handle_development_payment_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Sahkan transaksi Development dan aktifkan pelan."""

    query = update.callback_query

    if query is None:
        return

    await query.answer()

    telegram_user = update.effective_user

    if telegram_user is None:
        await query.answer(
            "Maklumat pengguna tidak dapat dibaca.",
            show_alert=True,
        )
        return

    if PAYMENT_PROVIDER != "DEVELOPMENT":
        await query.answer(
            "Pengesahan ujian tidak tersedia.",
            show_alert=True,
        )
        return

    try:
        payment_reference = (
            extract_payment_reference(
                query.data or ""
            )
        )

        await query.edit_message_text(
            "⏳ Mengesahkan pembayaran ujian..."
        )

        activated_subscription = (
            await asyncio.to_thread(
                confirm_development_payment,
                payment_reference,
                telegram_user.id,
            )
        )

        await query.edit_message_text(
            format_activation_success(
                activated_subscription
            )
        )

        logger.info(
            "Subscription Development diaktifkan. "
            "Telegram ID: %s | "
            "Payment: %s | "
            "Plan: %s | "
            "Subscription: %s",
            telegram_user.id,
            payment_reference,
            activated_subscription.plan_code.value,
            activated_subscription.subscription_id,
        )

    except PaymentServiceError as error:
        logger.exception(
            "Pengesahan pembayaran ujian gagal. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await query.edit_message_text(
            "Pengesahan pembayaran gagal.\n\n"
            f"{error}\n\n"
            "Sila cuba semula."
        )

    except Exception as error:
        logger.exception(
            "Ralat pengesahan pembayaran ujian. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await query.edit_message_text(
            "Pengesahan pembayaran gagal.\n\n"
            "Sila cuba semula."
        )