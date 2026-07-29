import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

from bayarcash_gateway import (
    BayarCashAPIError,
    BayarCashAuthenticationError,
    BayarCashClient,
    BayarCashError,
    BayarCashPaymentIntentRequest,
    BayarCashValidationError,
)
from billing_profile import (
    BillingProfile,
    get_billing_profile,
)
from config import PAYMENT_PROVIDER
from payment_config import (
    PaymentConfigurationError,
    load_bayarcash_config,
)
from payment_repository import (
    create_payment_record,
    get_payment_by_idempotency_key,
)
from payment_service import (
    CheckoutRequest,
    CheckoutSession,
    PaymentProviderCode,
    PaymentServiceError,
    PaymentStatus,
)
from plans import (
    BUSINESS_PLAN,
    STARTER_PLAN,
    Plan,
    PlanCode,
)
from subscription_service import (
    get_subscription_context,
)
from upgrade import (
    CALLBACK_CHECKOUT_CONFIRM_BUSINESS,
    CALLBACK_CHECKOUT_CONFIRM_STARTER,
    CALLBACK_UPGRADE_BACK,
    CHECKOUT_ORDER_NUMBER_KEY,
    CHECKOUT_PLAN_CODE_KEY,
    format_price,
    get_plan_icon,
)


logger = logging.getLogger(__name__)


CALLBACK_BAYARCASH_CONFIRM_PREFIX = (
    "upgrade:confirm:"
)


def get_confirmed_plan(
    callback_data: str,
) -> Plan | None:
    """Dapatkan pelan daripada callback checkout."""

    if (
        callback_data
        == CALLBACK_CHECKOUT_CONFIRM_STARTER
    ):
        return STARTER_PLAN

    if (
        callback_data
        == CALLBACK_CHECKOUT_CONFIRM_BUSINESS
    ):
        return BUSINESS_PLAN

    return None


def validate_billing_profile(
    billing_profile: BillingProfile,
) -> None:
    """Pastikan profil pembayaran lengkap."""

    if not billing_profile.full_name.strip():
        raise PaymentServiceError(
            "Nama Billing Profile tidak lengkap."
        )

    if not billing_profile.email.strip():
        raise PaymentServiceError(
            "Email Billing Profile tidak lengkap."
        )

    if not billing_profile.phone_number.strip():
        raise PaymentServiceError(
            "Nombor telefon Billing Profile "
            "tidak lengkap."
        )


def generate_internal_payment_reference() -> str:
    """
    Jana ID pembayaran dalaman ReceiptBot.

    BayarCash Payment Intent ID disimpan berasingan
    sebagai provider_reference.
    """

    return f"pay_{uuid4().hex}"


def build_idempotency_key(
    telegram_id: int,
    plan_code: PlanCode,
    order_number: str,
) -> str:
    """Bina kunci unik bagi satu checkout."""

    return (
        "bayarcash_checkout:"
        f"{telegram_id}:"
        f"{plan_code.value}:"
        f"{order_number}"
    )


def build_checkout_request(
    telegram_id: int,
    selected_plan: Plan,
    billing_profile: BillingProfile,
    order_number: str,
) -> CheckoutRequest:
    """Bina request dalaman ReceiptBot."""

    return CheckoutRequest(
        telegram_id=telegram_id,
        plan_code=selected_plan.code,
        customer_name=billing_profile.full_name,
        customer_email=billing_profile.email,
        customer_phone=(
            billing_profile.phone_number
        ),
        description=(
            "Langganan bulanan ReceiptBot "
            f"{selected_plan.name} — "
            f"{order_number}"
        ),
    )


def create_bayarcash_checkout(
    telegram_id: int,
    selected_plan: Plan,
    billing_profile: BillingProfile,
    order_number: str,
) -> CheckoutSession:
    """
    Cipta BayarCash Payment Intent dan simpan
    transaksi PENDING dalam Supabase.
    """

    validate_billing_profile(
        billing_profile
    )

    idempotency_key = build_idempotency_key(
        telegram_id=telegram_id,
        plan_code=selected_plan.code,
        order_number=order_number,
    )

    existing_payment = (
        get_payment_by_idempotency_key(
            idempotency_key
        )
    )

    if existing_payment is not None:
        if (
            existing_payment.telegram_id
            != telegram_id
        ):
            raise PaymentServiceError(
                "Transaksi ini dimiliki "
                "oleh pengguna lain."
            )

        if (
            existing_payment.plan_code
            != selected_plan.code
        ):
            raise PaymentServiceError(
                "Transaksi sedia ada menggunakan "
                "pelan yang berbeza."
            )

        if not existing_payment.checkout_url:
            raise PaymentServiceError(
                "Transaksi sedia ada tidak mempunyai "
                "pautan pembayaran."
            )

        return CheckoutSession(
            payment_reference=(
                existing_payment.payment_reference
            ),
            provider_code=(
                existing_payment.provider_code
            ),
            telegram_id=(
                existing_payment.telegram_id
            ),
            plan_code=(
                existing_payment.plan_code
            ),
            amount_rm=(
                existing_payment.amount_rm
            ),
            status=(
                existing_payment.status
            ),
            checkout_url=(
                existing_payment.checkout_url
            ),
            created_at=(
                existing_payment.created_at
            ),
            expires_at=(
                existing_payment.expires_at
            ),
        )

    config = load_bayarcash_config()

    payment_intent_request = (
        BayarCashPaymentIntentRequest(
            order_number=order_number,
            amount=selected_plan.monthly_price_rm,
            payer_name=billing_profile.full_name,
            payer_email=billing_profile.email,
            payer_telephone_number=(
                billing_profile.phone_number
            ),
            payment_channel=(
                config.payment_channel
            ),
            callback_url=(
                config.callback_url
            ),
            return_url=(
                config.return_url
            ),
        )
    )

    with BayarCashClient(
        config
    ) as client:
        payment_intent = (
            client.create_payment_intent(
                payment_intent_request
            )
        )

    internal_payment_reference = (
        generate_internal_payment_reference()
    )

    created_at = datetime.now(
        timezone.utc
    )

    checkout = CheckoutSession(
        payment_reference=(
            internal_payment_reference
        ),
        provider_code=(
            PaymentProviderCode.BAYARCASH
        ),
        telegram_id=telegram_id,
        plan_code=selected_plan.code,
        amount_rm=selected_plan.monthly_price_rm,
        status=PaymentStatus.PENDING,
        checkout_url=(
            payment_intent.checkout_url
        ),
        created_at=created_at,
        expires_at=None,
    )

    checkout_request = build_checkout_request(
        telegram_id=telegram_id,
        selected_plan=selected_plan,
        billing_profile=billing_profile,
        order_number=order_number,
    )

    payment_record = create_payment_record(
        request=checkout_request,
        checkout=checkout,
        idempotency_key=idempotency_key,
        provider_reference=(
            payment_intent.payment_intent_id
        ),
        metadata={
            "service": "bayarcash_checkout",
            "order_number": order_number,
            "billing_profile_id": (
                billing_profile.profile_id
            ),
            "payment_channel": (
                config.payment_channel
            ),
            "environment": (
                config.environment.value
            ),
        },
        provider_payload=(
            payment_intent.raw_payload
        ),
    )

    if not payment_record.checkout_url:
        raise PaymentServiceError(
            "Pautan BayarCash gagal disimpan."
        )

    logger.info(
        "BayarCash Payment Intent dicipta. "
        "Telegram ID: %s | "
        "Order: %s | "
        "Payment: %s | "
        "Provider Reference: %s | "
        "Plan: %s",
        telegram_id,
        order_number,
        payment_record.payment_reference,
        payment_intent.payment_intent_id,
        selected_plan.code.value,
    )

    return CheckoutSession(
        payment_reference=(
            payment_record.payment_reference
        ),
        provider_code=(
            payment_record.provider_code
        ),
        telegram_id=(
            payment_record.telegram_id
        ),
        plan_code=(
            payment_record.plan_code
        ),
        amount_rm=(
            payment_record.amount_rm
        ),
        status=(
            payment_record.status
        ),
        checkout_url=(
            payment_record.checkout_url
        ),
        created_at=(
            payment_record.created_at
        ),
        expires_at=(
            payment_record.expires_at
        ),
    )


def build_bayarcash_payment_keyboard(
    checkout_url: str,
) -> InlineKeyboardMarkup:
    """Bina butang untuk membuka BayarCash."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="💳 Bayar Sekarang",
                    url=checkout_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text=(
                        "⬅️ Kembali ke pilihan pelan"
                    ),
                    callback_data=(
                        CALLBACK_UPGRADE_BACK
                    ),
                )
            ],
        ]
    )


def format_bayarcash_checkout_message(
    selected_plan: Plan,
    checkout: CheckoutSession,
    order_number: str,
) -> str:
    """Sediakan paparan checkout BayarCash."""

    return (
        "💳 Pembayaran BayarCash\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Nombor Tempahan\n"
        f"{order_number}\n\n"
        "Pelan\n"
        f"{get_plan_icon(selected_plan.code)} "
        f"{selected_plan.name}\n\n"
        "Harga\n"
        f"{format_price(selected_plan.monthly_price_rm)}\n\n"
        "Status\n"
        "PENDING\n\n"
        "Rujukan ReceiptBot\n"
        f"{checkout.payment_reference}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Tekan Bayar Sekarang untuk meneruskan "
        "ke halaman pembayaran BayarCash.\n\n"
        "Pelan anda belum berubah.\n"
        "Pelan hanya akan diaktifkan selepas "
        "pembayaran berjaya disahkan."
    )


def clear_checkout_draft(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Padam draf checkout daripada memori."""

    context.user_data.pop(
        CHECKOUT_ORDER_NUMBER_KEY,
        None,
    )

    context.user_data.pop(
        CHECKOUT_PLAN_CODE_KEY,
        None,
    )


async def handle_bayarcash_checkout_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Cipta Payment Intent selepas review disahkan."""

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

    if PAYMENT_PROVIDER != "BAYARCASH":
        await query.answer(
            "BayarCash tidak aktif.",
            show_alert=True,
        )
        return

    callback_data = query.data or ""

    selected_plan = get_confirmed_plan(
        callback_data
    )

    if selected_plan is None:
        await query.answer(
            "Pilihan pelan tidak dikenali.",
            show_alert=True,
        )
        return

    try:
        subscription = await asyncio.to_thread(
            get_subscription_context,
            telegram_user.id,
        )

        if (
            subscription.plan_code
            == selected_plan.code
        ):
            clear_checkout_draft(
                context
            )

            await query.edit_message_text(
                "✅ Anda sudah menggunakan "
                f"pelan {selected_plan.name}."
            )
            return

        stored_plan_code = (
            context.user_data.get(
                CHECKOUT_PLAN_CODE_KEY
            )
        )

        order_number = (
            context.user_data.get(
                CHECKOUT_ORDER_NUMBER_KEY
            )
        )

        if (
            stored_plan_code
            != selected_plan.code.value
            or not isinstance(
                order_number,
                str,
            )
            or not order_number.strip()
        ):
            raise PaymentServiceError(
                "Sesi checkout telah tamat.\n\n"
                "Gunakan /upgrade untuk "
                "memulakan semula."
            )

        billing_profile = await asyncio.to_thread(
            get_billing_profile,
            telegram_user.id,
        )

        if billing_profile is None:
            raise PaymentServiceError(
                "Billing Profile belum lengkap.\n\n"
                "Gunakan /billing dahulu."
            )

        await query.edit_message_text(
            "⏳ Menghubungkan ke BayarCash..."
        )

        checkout = await asyncio.to_thread(
            create_bayarcash_checkout,
            telegram_user.id,
            selected_plan,
            billing_profile,
            order_number,
        )

        await query.edit_message_text(
            text=format_bayarcash_checkout_message(
                selected_plan=selected_plan,
                checkout=checkout,
                order_number=order_number,
            ),
            reply_markup=(
                build_bayarcash_payment_keyboard(
                    checkout.checkout_url
                )
            ),
        )

        clear_checkout_draft(
            context
        )

    except PaymentConfigurationError as error:
        logger.exception(
            "Konfigurasi BayarCash tidak lengkap. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await query.edit_message_text(
            "Konfigurasi pembayaran belum lengkap.\n\n"
            "Sila hubungi sokongan ReceiptBot."
        )

    except BayarCashAuthenticationError as error:
        logger.exception(
            "Credential BayarCash ditolak. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await query.edit_message_text(
            "BayarCash tidak dapat mengesahkan "
            "akaun merchant.\n\n"
            "Sila hubungi sokongan ReceiptBot."
        )

    except BayarCashValidationError as error:
        logger.exception(
            "Data Payment Intent tidak sah. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await query.edit_message_text(
            "Maklumat pembayaran tidak sah.\n\n"
            f"{error}"
        )

    except (
        BayarCashAPIError,
        BayarCashError,
    ) as error:
        logger.exception(
            "BayarCash gagal mencipta checkout. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await query.edit_message_text(
            "BayarCash tidak dapat dihubungi.\n\n"
            "Sila cuba semula sebentar lagi."
        )

    except PaymentServiceError as error:
        logger.exception(
            "Checkout BayarCash gagal. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await query.edit_message_text(
            "Checkout gagal diproses.\n\n"
            f"{error}"
        )

    except Exception as error:
        logger.exception(
            "Ralat tidak dijangka semasa checkout. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await query.edit_message_text(
            "Checkout gagal diproses.\n\n"
            "Sila cuba semula."
        )