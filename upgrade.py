import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

from billing_profile import (
    BillingProfile,
    get_billing_profile,
)
from config import PAYMENT_PROVIDER
from development_payment import (
    build_development_confirmation_keyboard,
)
from payment_service import (
    CheckoutRequest,
    CheckoutSession,
    PaymentProviderNotConfiguredError,
    PaymentServiceError,
    create_checkout,
)
from plans import (
    BUSINESS_PLAN,
    FREE_PLAN,
    STARTER_PLAN,
    Plan,
    PlanCode,
)
from subscription_service import (
    SubscriptionContext,
    get_subscription_context,
)


logger = logging.getLogger(__name__)

MALAYSIA_TIMEZONE = ZoneInfo(
    "Asia/Kuching"
)


# =========================================================
# CALLBACK DATA
# =========================================================

CALLBACK_UPGRADE_PREFIX = "upgrade:"

CALLBACK_UPGRADE_STARTER = (
    "upgrade:STARTER"
)

CALLBACK_UPGRADE_BUSINESS = (
    "upgrade:BUSINESS"
)

CALLBACK_UPGRADE_BACK = (
    "upgrade:BACK"
)

CALLBACK_CHECKOUT_CONFIRM_STARTER = (
    "upgrade:confirm:STARTER"
)

CALLBACK_CHECKOUT_CONFIRM_BUSINESS = (
    "upgrade:confirm:BUSINESS"
)

CALLBACK_CHECKOUT_CANCEL = (
    "upgrade:checkout:cancel"
)


# =========================================================
# TEMPORARY CONTEXT KEYS
# =========================================================

CHECKOUT_ORDER_NUMBER_KEY = (
    "checkout_order_number"
)

CHECKOUT_PLAN_CODE_KEY = (
    "checkout_plan_code"
)


# =========================================================
# PLAN DISPLAY
# =========================================================

def format_price(
    price: Decimal,
) -> str:
    """Format harga langganan."""

    if price == 0:
        return "RM0"

    return f"RM{price:.2f} / bulan"


def get_plan_icon(
    plan_code: PlanCode,
) -> str:
    """Dapatkan ikon pelan."""

    if plan_code == PlanCode.STARTER:
        return "⭐"

    if plan_code == PlanCode.BUSINESS:
        return "⭐⭐"

    return "🆓"


def get_plan_features(
    plan_code: PlanCode,
) -> tuple[str, ...]:
    """Dapatkan ciri utama pelan."""

    if plan_code == PlanCode.FREE:
        return (
            "20 resit setiap bulan",
            "AI membaca resit",
            "AI kategori automatik",
            "Dashboard asas",
            "Ringkasan bulanan",
            "10 resit terkini",
            "Simpan gambar 30 hari",
        )

    if plan_code == PlanCode.STARTER:
        return (
            "100 resit setiap bulan",
            "Semua fungsi asas",
            "Carian resit",
            "Edit dan padam rekod",
            "Eksport CSV",
            "Dashboard penuh",
            "Simpan gambar 1 tahun",
        )

    return (
        "500 resit setiap bulan",
        "Semua fungsi Starter",
        "Eksport CSV dan Excel",
        "Eksport laporan PDF",
        "Kategori tersuai",
        "Rekod pendapatan dan perbelanjaan",
        "Simpan gambar selagi melanggan",
    )


def format_plan_section(
    plan: Plan,
    current_plan_code: PlanCode,
) -> str:
    """Format satu bahagian pelan."""

    feature_lines = "\n".join(
        f"✓ {feature}"
        for feature in get_plan_features(
            plan.code
        )
    )

    plan_status = ""

    if plan.code == current_plan_code:
        plan_status = (
            "\n\n✅ Pelan semasa anda"
        )

    return (
        f"{get_plan_icon(plan.code)} "
        f"{plan.name}\n"
        f"{format_price(plan.monthly_price_rm)}\n\n"
        f"{feature_lines}"
        f"{plan_status}"
    )


def format_upgrade_message(
    subscription: SubscriptionContext,
) -> str:
    """Sediakan paparan Upgrade Center."""

    sections = [
        format_plan_section(
            FREE_PLAN,
            subscription.plan_code,
        ),
        format_plan_section(
            STARTER_PLAN,
            subscription.plan_code,
        ),
        format_plan_section(
            BUSINESS_PLAN,
            subscription.plan_code,
        ),
    ]

    if PAYMENT_PROVIDER == "DEVELOPMENT":
        payment_notice = (
            "🧪 Mod ujian pembayaran aktif.\n"
            "Tiada wang sebenar akan diterima."
        )

    elif PAYMENT_PROVIDER == "BAYARCASH":
        payment_notice = (
            "💳 Pembayaran akan diproses "
            "melalui BayarCash."
        )

    else:
        payment_notice = (
            "Pembayaran dalam talian belum tersedia."
        )

    return (
        "🚀 Upgrade ReceiptBot\n\n"
        "Pilih pelan yang sesuai dengan "
        "keperluan anda.\n\n"
        "━━━━━━━━━━━━━━\n\n"
        + "\n\n━━━━━━━━━━━━━━\n\n".join(
            sections
        )
        + "\n\n━━━━━━━━━━━━━━\n\n"
        f"{payment_notice}"
    )


# =========================================================
# KEYBOARDS
# =========================================================

def build_upgrade_keyboard(
    current_plan_code: PlanCode,
) -> InlineKeyboardMarkup | None:
    """Bina butang pilihan pelan."""

    rows: list[
        list[InlineKeyboardButton]
    ] = []

    if current_plan_code == PlanCode.FREE:
        rows.append(
            [
                InlineKeyboardButton(
                    text=(
                        "⭐ Pilih Starter — RM9.90"
                    ),
                    callback_data=(
                        CALLBACK_UPGRADE_STARTER
                    ),
                )
            ]
        )

        rows.append(
            [
                InlineKeyboardButton(
                    text=(
                        "⭐⭐ Pilih Business — RM19.90"
                    ),
                    callback_data=(
                        CALLBACK_UPGRADE_BUSINESS
                    ),
                )
            ]
        )

    elif current_plan_code == PlanCode.STARTER:
        rows.append(
            [
                InlineKeyboardButton(
                    text=(
                        "⭐⭐ Upgrade Business — RM19.90"
                    ),
                    callback_data=(
                        CALLBACK_UPGRADE_BUSINESS
                    ),
                )
            ]
        )

    if not rows:
        return None

    return InlineKeyboardMarkup(
        rows
    )


def build_back_keyboard() -> InlineKeyboardMarkup:
    """Bina butang kembali ke Upgrade Center."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=(
                        "⬅️ Kembali ke pilihan pelan"
                    ),
                    callback_data=(
                        CALLBACK_UPGRADE_BACK
                    ),
                )
            ]
        ]
    )


def build_missing_billing_keyboard() -> InlineKeyboardMarkup:
    """Bina butang kembali apabila Billing Profile tiada."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="⬅️ Kembali",
                    callback_data=(
                        CALLBACK_UPGRADE_BACK
                    ),
                )
            ]
        ]
    )


def build_checkout_review_keyboard(
    plan_code: PlanCode,
) -> InlineKeyboardMarkup:
    """Bina butang pengesahan ringkasan tempahan."""

    if plan_code == PlanCode.STARTER:
        confirm_callback = (
            CALLBACK_CHECKOUT_CONFIRM_STARTER
        )

    elif plan_code == PlanCode.BUSINESS:
        confirm_callback = (
            CALLBACK_CHECKOUT_CONFIRM_BUSINESS
        )

    else:
        raise PaymentServiceError(
            "Pelan ini tidak memerlukan pembayaran."
        )

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="✅ Teruskan Pembayaran",
                    callback_data=(
                        confirm_callback
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Kemas Kini Billing Profile",
                    callback_data=(
                        CALLBACK_CHECKOUT_CANCEL
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Kembali ke pilihan pelan",
                    callback_data=(
                        CALLBACK_UPGRADE_BACK
                    ),
                )
            ],
        ]
    )


# =========================================================
# PLAN RESOLUTION
# =========================================================

def get_selected_plan_from_callback(
    callback_data: str,
) -> Plan | None:
    """Dapatkan pelan daripada callback pilihan."""

    if callback_data == CALLBACK_UPGRADE_STARTER:
        return STARTER_PLAN

    if callback_data == CALLBACK_UPGRADE_BUSINESS:
        return BUSINESS_PLAN

    return None


def get_confirmed_plan_from_callback(
    callback_data: str,
) -> Plan | None:
    """Dapatkan pelan daripada callback pengesahan."""

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


# =========================================================
# ORDER NUMBER
# =========================================================

def generate_order_number(
    plan_code: PlanCode,
) -> str:
    """
    Jana nombor tempahan rasmi ReceiptBot.

    Format:
    RB-YYMMDD-PLAN-XXXXXX

    Contoh:
    RB-260728-BUS-A1B2C3
    """

    local_date = datetime.now(
        MALAYSIA_TIMEZONE
    ).strftime(
        "%y%m%d"
    )

    if plan_code == PlanCode.STARTER:
        plan_short_code = "STR"

    elif plan_code == PlanCode.BUSINESS:
        plan_short_code = "BUS"

    else:
        raise PaymentServiceError(
            "Pelan tidak sah untuk nombor tempahan."
        )

    random_suffix = (
        uuid4().hex[:6].upper()
    )

    order_number = (
        f"RB-{local_date}-"
        f"{plan_short_code}-"
        f"{random_suffix}"
    )

    if len(order_number) > 30:
        raise PaymentServiceError(
            "Nombor tempahan melebihi had."
        )

    return order_number


def clear_checkout_draft(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Padam draf checkout daripada memori pengguna."""

    context.user_data.pop(
        CHECKOUT_ORDER_NUMBER_KEY,
        None,
    )

    context.user_data.pop(
        CHECKOUT_PLAN_CODE_KEY,
        None,
    )


def save_checkout_draft(
    context: ContextTypes.DEFAULT_TYPE,
    order_number: str,
    plan_code: PlanCode,
) -> None:
    """Simpan draf ringkasan checkout."""

    context.user_data[
        CHECKOUT_ORDER_NUMBER_KEY
    ] = order_number

    context.user_data[
        CHECKOUT_PLAN_CODE_KEY
    ] = plan_code.value


def get_checkout_order_number(
    context: ContextTypes.DEFAULT_TYPE,
    plan_code: PlanCode,
) -> str:
    """
    Dapatkan order number sedia ada jika sepadan.

    Jika tiada, jana order number baharu.
    """

    stored_plan_code = context.user_data.get(
        CHECKOUT_PLAN_CODE_KEY
    )

    stored_order_number = context.user_data.get(
        CHECKOUT_ORDER_NUMBER_KEY
    )

    if (
        stored_plan_code == plan_code.value
        and isinstance(
            stored_order_number,
            str,
        )
        and stored_order_number.strip()
    ):
        return stored_order_number

    order_number = generate_order_number(
        plan_code
    )

    save_checkout_draft(
        context=context,
        order_number=order_number,
        plan_code=plan_code,
    )

    return order_number


# =========================================================
# BILLING PROFILE
# =========================================================

def validate_billing_profile(
    profile: BillingProfile,
) -> None:
    """Pastikan Billing Profile lengkap."""

    if not profile.full_name.strip():
        raise PaymentServiceError(
            "Nama Billing Profile tidak lengkap."
        )

    if not profile.email.strip():
        raise PaymentServiceError(
            "Email Billing Profile tidak lengkap."
        )

    if not profile.phone_number.strip():
        raise PaymentServiceError(
            "Nombor telefon Billing Profile "
            "tidak lengkap."
        )


def format_missing_billing_profile() -> str:
    """Mesej jika Billing Profile belum lengkap."""

    return (
        "💳 Billing Profile Diperlukan\n\n"
        "Sebelum meneruskan pembayaran, "
        "ReceiptBot memerlukan:\n\n"
        "• Nama\n"
        "• Email\n"
        "• Nombor telefon\n\n"
        "Gunakan command berikut dahulu:\n\n"
        "/billing\n\n"
        "Selepas maklumat berjaya disimpan, "
        "gunakan /upgrade semula."
    )


# =========================================================
# CHECKOUT REVIEW
# =========================================================

def get_payment_method_label() -> str:
    """Dapatkan nama kaedah pembayaran."""

    if PAYMENT_PROVIDER == "BAYARCASH":
        return (
            "BayarCash\n"
            "FPX / DuitNow"
        )

    if PAYMENT_PROVIDER == "DEVELOPMENT":
        return (
            "Development Gateway\n"
            "Transaksi ujian"
        )

    return "Belum dikonfigurasi"


def format_checkout_review(
    selected_plan: Plan,
    billing_profile: BillingProfile,
    order_number: str,
) -> str:
    """Sediakan ringkasan tempahan sebelum checkout."""

    return (
        "💳 Ringkasan Tempahan\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Nombor Tempahan\n"
        f"{order_number}\n\n"
        "Pelan\n"
        f"{get_plan_icon(selected_plan.code)} "
        f"{selected_plan.name}\n\n"
        "Harga\n"
        f"{format_price(selected_plan.monthly_price_rm)}\n\n"
        "Kuota\n"
        f"{selected_plan.monthly_receipt_limit} "
        "resit / bulan\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Nama\n"
        f"{billing_profile.full_name}\n\n"
        "Email\n"
        f"{billing_profile.email}\n\n"
        "Nombor Telefon\n"
        f"{billing_profile.phone_number}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Kaedah Pembayaran\n"
        f"{get_payment_method_label()}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Dengan meneruskan, anda mengesahkan "
        "maklumat di atas adalah betul dan "
        f"bersetuju melanggan ReceiptBot "
        f"{selected_plan.name} pada harga "
        f"{format_price(selected_plan.monthly_price_rm)}."
    )


# =========================================================
# DEVELOPMENT CHECKOUT
# =========================================================

def build_checkout_idempotency_key(
    telegram_id: int,
    plan_code: PlanCode,
    order_number: str,
) -> str:
    """Bina idempotency key checkout."""

    return (
        f"telegram_upgrade:"
        f"{telegram_id}:"
        f"{plan_code.value}:"
        f"{order_number}"
    )


def create_development_checkout(
    telegram_id: int,
    selected_plan: Plan,
    billing_profile: BillingProfile,
    order_number: str,
) -> CheckoutSession:
    """Cipta checkout Development selepas review."""

    request = CheckoutRequest(
        telegram_id=telegram_id,
        plan_code=selected_plan.code,
        customer_name=(
            billing_profile.full_name
        ),
        customer_email=(
            billing_profile.email
        ),
        customer_phone=(
            billing_profile.phone_number
        ),
        description=(
            "Langganan bulanan ReceiptBot "
            f"{selected_plan.name} — "
            f"{order_number}"
        ),
    )

    return create_checkout(
        request=request,
        idempotency_key=(
            build_checkout_idempotency_key(
                telegram_id=telegram_id,
                plan_code=selected_plan.code,
                order_number=order_number,
            )
        ),
    )


def format_checkout_message(
    selected_plan: Plan,
    checkout: CheckoutSession,
    order_number: str,
) -> str:
    """Sediakan mesej checkout Development."""

    return (
        "🧾 Checkout ReceiptBot\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Nombor Tempahan\n"
        f"{order_number}\n\n"
        "Pelan\n"
        f"{get_plan_icon(selected_plan.code)} "
        f"{selected_plan.name}\n\n"
        "Harga\n"
        f"{format_price(selected_plan.monthly_price_rm)}\n\n"
        "Kuota\n"
        f"{selected_plan.monthly_receipt_limit} "
        "resit / bulan\n\n"
        "Status\n"
        f"{checkout.status.value}\n\n"
        "Rujukan Pembayaran\n"
        f"{checkout.payment_reference}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "🧪 Ini ialah transaksi ujian.\n"
        "Tiada wang sebenar akan ditolak.\n\n"
        "Tekan butang pengesahan di bawah "
        "untuk menguji pengaktifan pelan.\n\n"
        "Pelan hanya akan berubah selepas "
        "pembayaran ujian disahkan."
    )


# =========================================================
# TELEGRAM COMMAND
# =========================================================

async def upgrade_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Paparkan Upgrade Center."""

    if update.message is None:
        return

    telegram_user = update.effective_user

    if telegram_user is None:
        await update.message.reply_text(
            "Maklumat pengguna tidak dapat dibaca."
        )
        return

    clear_checkout_draft(
        context
    )

    status_message = await update.message.reply_text(
        "⏳ Menyediakan pilihan pelan..."
    )

    try:
        subscription = await asyncio.to_thread(
            get_subscription_context,
            telegram_user.id,
        )

        await status_message.edit_text(
            text=format_upgrade_message(
                subscription
            ),
            reply_markup=build_upgrade_keyboard(
                subscription.plan_code
            ),
        )

    except Exception as error:
        logger.exception(
            "Upgrade Center gagal. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await status_message.edit_text(
            "Pilihan pelan gagal dipaparkan.\n\n"
            "Sila cuba semula."
        )


# =========================================================
# CALLBACK HANDLER
# =========================================================

async def handle_upgrade_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Proses pilihan dan pengesahan checkout."""

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

    callback_data = query.data or ""

    try:
        subscription = await asyncio.to_thread(
            get_subscription_context,
            telegram_user.id,
        )

        # -------------------------------------------------
        # KEMBALI KE UPGRADE CENTER
        # -------------------------------------------------

        if callback_data == CALLBACK_UPGRADE_BACK:
            clear_checkout_draft(
                context
            )

            await query.edit_message_text(
                text=format_upgrade_message(
                    subscription
                ),
                reply_markup=build_upgrade_keyboard(
                    subscription.plan_code
                ),
            )
            return

        # -------------------------------------------------
        # KEMAS KINI BILLING PROFILE
        # -------------------------------------------------

        if callback_data == CALLBACK_CHECKOUT_CANCEL:
            clear_checkout_draft(
                context
            )

            await query.edit_message_text(
                "✏️ Kemas Kini Billing Profile\n\n"
                "Gunakan command berikut:\n\n"
                "/billing\n\n"
                "Selepas maklumat dikemas kini, "
                "gunakan /upgrade semula.",
                reply_markup=(
                    build_missing_billing_keyboard()
                ),
            )
            return

        # -------------------------------------------------
        # PILIH PELAN → PAPAR REVIEW
        # -------------------------------------------------

        selected_plan = (
            get_selected_plan_from_callback(
                callback_data
            )
        )

        if selected_plan is not None:
            if (
                selected_plan.code
                == subscription.plan_code
            ):
                await query.edit_message_text(
                    text=(
                        "✅ Anda sudah menggunakan "
                        f"pelan {selected_plan.name}."
                    ),
                    reply_markup=(
                        build_back_keyboard()
                    ),
                )
                return

            billing_profile = (
                await asyncio.to_thread(
                    get_billing_profile,
                    telegram_user.id,
                )
            )

            if billing_profile is None:
                await query.edit_message_text(
                    text=(
                        format_missing_billing_profile()
                    ),
                    reply_markup=(
                        build_missing_billing_keyboard()
                    ),
                )
                return

            validate_billing_profile(
                billing_profile
            )

            order_number = (
                get_checkout_order_number(
                    context=context,
                    plan_code=selected_plan.code,
                )
            )

            await query.edit_message_text(
                text=format_checkout_review(
                    selected_plan=selected_plan,
                    billing_profile=(
                        billing_profile
                    ),
                    order_number=order_number,
                ),
                reply_markup=(
                    build_checkout_review_keyboard(
                        selected_plan.code
                    )
                ),
            )
            return

        # -------------------------------------------------
        # SAHKAN REVIEW → CIPTA CHECKOUT
        # -------------------------------------------------

        confirmed_plan = (
            get_confirmed_plan_from_callback(
                callback_data
            )
        )

        if confirmed_plan is not None:
            if (
                confirmed_plan.code
                == subscription.plan_code
            ):
                clear_checkout_draft(
                    context
                )

                await query.edit_message_text(
                    text=(
                        "✅ Anda sudah menggunakan "
                        f"pelan {confirmed_plan.name}."
                    ),
                    reply_markup=(
                        build_back_keyboard()
                    ),
                )
                return

            billing_profile = (
                await asyncio.to_thread(
                    get_billing_profile,
                    telegram_user.id,
                )
            )

            if billing_profile is None:
                clear_checkout_draft(
                    context
                )

                await query.edit_message_text(
                    text=(
                        format_missing_billing_profile()
                    ),
                    reply_markup=(
                        build_missing_billing_keyboard()
                    ),
                )
                return

            validate_billing_profile(
                billing_profile
            )

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
                != confirmed_plan.code.value
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

            await query.edit_message_text(
                "⏳ Menyediakan checkout..."
            )

            if PAYMENT_PROVIDER == "DEVELOPMENT":
                checkout = await asyncio.to_thread(
                    create_development_checkout,
                    telegram_user.id,
                    confirmed_plan,
                    billing_profile,
                    order_number,
                )

                await query.edit_message_text(
                    text=format_checkout_message(
                        selected_plan=confirmed_plan,
                        checkout=checkout,
                        order_number=order_number,
                    ),
                    reply_markup=(
                        build_development_confirmation_keyboard(
                            checkout.payment_reference
                        )
                    ),
                )

                clear_checkout_draft(
                    context
                )
                return

            if PAYMENT_PROVIDER == "BAYARCASH":
                await query.edit_message_text(
                    text=(
                        "✅ Ringkasan Tempahan Disahkan\n\n"
                        "━━━━━━━━━━━━━━\n\n"
                        "Nombor Tempahan\n"
                        f"{order_number}\n\n"
                        "Pelan\n"
                        f"{get_plan_icon(confirmed_plan.code)} "
                        f"{confirmed_plan.name}\n\n"
                        "Harga\n"
                        f"{format_price(confirmed_plan.monthly_price_rm)}\n\n"
                        "━━━━━━━━━━━━━━\n\n"
                        "Integrasi Payment Intent BayarCash "
                        "akan disambungkan dalam task "
                        "seterusnya.\n\n"
                        "Tiada bayaran atau perubahan pelan "
                        "telah dibuat."
                    ),
                    reply_markup=(
                        build_back_keyboard()
                    ),
                )

                clear_checkout_draft(
                    context
                )
                return

            raise PaymentProviderNotConfiguredError(
                "Payment gateway belum dikonfigurasi."
            )

        # -------------------------------------------------
        # CALLBACK TIDAK DIKENALI
        # -------------------------------------------------

        await query.answer(
            "Pilihan tidak dikenali.",
            show_alert=True,
        )

    except PaymentProviderNotConfiguredError:
        clear_checkout_draft(
            context
        )

        await query.edit_message_text(
            "⚠️ Pembayaran Belum Tersedia\n\n"
            "Payment gateway belum dikonfigurasi.",
            reply_markup=build_back_keyboard(),
        )

    except PaymentServiceError as error:
        logger.exception(
            "Checkout ReceiptBot gagal. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        clear_checkout_draft(
            context
        )

        await query.edit_message_text(
            "Checkout gagal diproses.\n\n"
            f"{error}",
            reply_markup=build_back_keyboard(),
        )

    except Exception as error:
        logger.exception(
            "Pilihan upgrade gagal. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        clear_checkout_draft(
            context
        )

        await query.edit_message_text(
            "Pilihan pelan gagal diproses.\n\n"
            "Sila cuba semula.",
            reply_markup=build_back_keyboard(),
        )