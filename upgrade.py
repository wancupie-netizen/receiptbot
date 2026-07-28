import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

from config import PAYMENT_PROVIDER
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


def format_price(
    price: Decimal,
) -> str:
    """Format harga pelan."""

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
    """Dapatkan ciri utama untuk paparan Upgrade Center."""

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

    icon = get_plan_icon(
        plan.code
    )

    features = get_plan_features(
        plan.code
    )

    feature_lines = "\n".join(
        f"✓ {feature}"
        for feature in features
    )

    if plan.code == current_plan_code:
        plan_status = (
            "\n\n✅ Pelan semasa anda"
        )
    else:
        plan_status = ""

    return (
        f"{icon} {plan.name}\n"
        f"{format_price(plan.monthly_price_rm)}\n\n"
        f"{feature_lines}"
        f"{plan_status}"
    )


def format_upgrade_message(
    subscription: SubscriptionContext,
) -> str:
    """Sediakan paparan penuh Upgrade Center."""

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
    else:
        payment_notice = (
            "Pembayaran dalam talian akan "
            "tersedia tidak lama lagi."
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


def build_upgrade_keyboard(
    current_plan_code: PlanCode,
) -> InlineKeyboardMarkup | None:
    """Bina butang berdasarkan pelan semasa."""

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
    """Bina butang kembali ke pilihan pelan."""

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


def build_checkout_idempotency_key(
    telegram_id: int,
    plan_code: PlanCode,
) -> str:
    """
    Bina kunci checkout harian.

    Klik berulang pada pelan sama dalam hari yang sama
    akan menggunakan transaksi PENDING yang sama.
    """

    local_date = datetime.now(
        MALAYSIA_TIMEZONE
    ).strftime(
        "%Y%m%d"
    )

    return (
        f"telegram_upgrade:"
        f"{telegram_id}:"
        f"{plan_code.value}:"
        f"{local_date}"
    )


def create_development_checkout(
    telegram_id: int,
    customer_name: str,
    selected_plan: Plan,
) -> CheckoutSession:
    """Cipta checkout ujian dan simpan ke Supabase."""

    checkout_request = CheckoutRequest(
        telegram_id=telegram_id,
        plan_code=selected_plan.code,
        customer_name=customer_name,
        description=(
            "Langganan bulanan ReceiptBot "
            f"{selected_plan.name}"
        ),
    )

    idempotency_key = (
        build_checkout_idempotency_key(
            telegram_id=telegram_id,
            plan_code=selected_plan.code,
        )
    )

    return create_checkout(
        request=checkout_request,
        idempotency_key=idempotency_key,
    )


def format_checkout_message(
    selected_plan: Plan,
    checkout: CheckoutSession,
) -> str:
    """Sediakan paparan transaksi checkout."""

    if PAYMENT_PROVIDER == "DEVELOPMENT":
        provider_notice = (
            "🧪 Ini ialah transaksi ujian.\n"
            "Tiada wang sebenar akan ditolak."
        )
    else:
        provider_notice = (
            "Gunakan pautan checkout untuk "
            "meneruskan pembayaran."
        )

    return (
        "🧾 Checkout ReceiptBot\n\n"
        "━━━━━━━━━━━━━━\n\n"
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
        f"{provider_notice}\n\n"
        "Pelan akaun anda belum berubah.\n"
        "Pelan hanya akan diaktifkan selepas "
        "pembayaran disahkan."
    )


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

    status_message = await update.message.reply_text(
        "⏳ Menyediakan pilihan pelan..."
    )

    try:
        subscription = await asyncio.to_thread(
            get_subscription_context,
            telegram_user.id,
        )

        keyboard = build_upgrade_keyboard(
            subscription.plan_code
        )

        await status_message.edit_text(
            text=format_upgrade_message(
                subscription
            ),
            reply_markup=keyboard,
        )

    except Exception as error:
        logger.exception(
            "Gagal menyediakan Upgrade Center. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await status_message.edit_text(
            "Pilihan pelan gagal dipaparkan.\n\n"
            "Sila cuba semula."
        )


async def handle_upgrade_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Proses pilihan pelan daripada butang inline."""

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

    callback_data = (
        query.data or ""
    )

    try:
        subscription = await asyncio.to_thread(
            get_subscription_context,
            telegram_user.id,
        )

        if callback_data == CALLBACK_UPGRADE_BACK:
            keyboard = build_upgrade_keyboard(
                subscription.plan_code
            )

            await query.edit_message_text(
                text=format_upgrade_message(
                    subscription
                ),
                reply_markup=keyboard,
            )
            return

        if (
            callback_data
            == CALLBACK_UPGRADE_STARTER
        ):
            selected_plan = STARTER_PLAN

        elif (
            callback_data
            == CALLBACK_UPGRADE_BUSINESS
        ):
            selected_plan = BUSINESS_PLAN

        else:
            await query.answer(
                "Pilihan pelan tidak dikenali.",
                show_alert=True,
            )
            return

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

        customer_name = (
            telegram_user.full_name
            or telegram_user.first_name
            or "Pengguna ReceiptBot"
        )

        await query.edit_message_text(
            text=(
                "⏳ Mencipta transaksi "
                f"{selected_plan.name}..."
            )
        )

        checkout = await asyncio.to_thread(
            create_development_checkout,
            telegram_user.id,
            customer_name,
            selected_plan,
        )

        await query.edit_message_text(
            text=format_checkout_message(
                selected_plan=selected_plan,
                checkout=checkout,
            ),
            reply_markup=(
                build_back_keyboard()
            ),
        )

        logger.info(
            "Checkout upgrade dicipta. "
            "Telegram ID: %s | "
            "Pelan: %s | "
            "Reference: %s | "
            "Status: %s",
            telegram_user.id,
            selected_plan.code.value,
            checkout.payment_reference,
            checkout.status.value,
        )

    except PaymentProviderNotConfiguredError:
        await query.edit_message_text(
            text=(
                "⚠️ Pembayaran Belum Tersedia\n\n"
                "Payment gateway belum "
                "dikonfigurasi.\n\n"
                "Sila cuba semula selepas sistem "
                "pembayaran dilancarkan."
            ),
            reply_markup=(
                build_back_keyboard()
            ),
        )

    except PaymentServiceError as error:
        logger.exception(
            "Payment Service gagal memproses upgrade. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await query.edit_message_text(
            text=(
                "Checkout gagal dicipta.\n\n"
                f"{error}\n\n"
                "Sila cuba semula."
            ),
            reply_markup=(
                build_back_keyboard()
            ),
        )

    except Exception as error:
        logger.exception(
            "Gagal memproses pilihan upgrade. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await query.edit_message_text(
            text=(
                "Pilihan pelan gagal diproses.\n\n"
                "Sila cuba semula."
            ),
            reply_markup=(
                build_back_keyboard()
            ),
        )