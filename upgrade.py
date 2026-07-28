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

CALLBACK_UPGRADE_PREFIX = "upgrade:"
CALLBACK_UPGRADE_STARTER = "upgrade:STARTER"
CALLBACK_UPGRADE_BUSINESS = "upgrade:BUSINESS"
CALLBACK_UPGRADE_BACK = "upgrade:BACK"


def format_price(
    price: Decimal,
) -> str:
    if price == 0:
        return "RM0"

    return f"RM{price:.2f} / bulan"


def get_plan_icon(
    plan_code: PlanCode,
) -> str:
    if plan_code == PlanCode.STARTER:
        return "⭐"

    if plan_code == PlanCode.BUSINESS:
        return "⭐⭐"

    return "🆓"


def get_plan_features(
    plan_code: PlanCode,
) -> tuple[str, ...]:
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
    rows: list[
        list[InlineKeyboardButton]
    ] = []

    if current_plan_code == PlanCode.FREE:
        rows.append(
            [
                InlineKeyboardButton(
                    text="⭐ Pilih Starter — RM9.90",
                    callback_data=(
                        CALLBACK_UPGRADE_STARTER
                    ),
                )
            ]
        )

        rows.append(
            [
                InlineKeyboardButton(
                    text="⭐⭐ Pilih Business — RM19.90",
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
    request = CheckoutRequest(
        telegram_id=telegram_id,
        plan_code=selected_plan.code,
        customer_name=customer_name,
        description=(
            "Langganan bulanan ReceiptBot "
            f"{selected_plan.name}"
        ),
    )

    return create_checkout(
        request=request,
        idempotency_key=(
            build_checkout_idempotency_key(
                telegram_id,
                selected_plan.code,
            )
        ),
    )


def format_checkout_message(
    selected_plan: Plan,
    checkout: CheckoutSession,
) -> str:
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
        "🧪 Ini ialah transaksi ujian.\n"
        "Tiada wang sebenar akan ditolak.\n\n"
        "Tekan butang pengesahan di bawah "
        "untuk menguji pengaktifan pelan.\n\n"
        "Pelan hanya akan berubah selepas "
        "pembayaran ujian disahkan."
    )


async def upgrade_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
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
            "Upgrade Center gagal: %s",
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
    query = update.callback_query

    if query is None:
        return

    await query.answer()

    telegram_user = update.effective_user

    if telegram_user is None:
        return

    try:
        subscription = await asyncio.to_thread(
            get_subscription_context,
            telegram_user.id,
        )

        callback_data = query.data or ""

        if callback_data == CALLBACK_UPGRADE_BACK:
            await query.edit_message_text(
                text=format_upgrade_message(
                    subscription
                ),
                reply_markup=build_upgrade_keyboard(
                    subscription.plan_code
                ),
            )
            return

        if callback_data == CALLBACK_UPGRADE_STARTER:
            selected_plan = STARTER_PLAN

        elif callback_data == CALLBACK_UPGRADE_BUSINESS:
            selected_plan = BUSINESS_PLAN

        else:
            await query.answer(
                "Pilihan pelan tidak dikenali.",
                show_alert=True,
            )
            return

        if selected_plan.code == subscription.plan_code:
            await query.edit_message_text(
                text=(
                    "✅ Anda sudah menggunakan "
                    f"pelan {selected_plan.name}."
                ),
                reply_markup=build_back_keyboard(),
            )
            return

        await query.edit_message_text(
            "⏳ Mencipta transaksi..."
        )

        checkout = await asyncio.to_thread(
            create_development_checkout,
            telegram_user.id,
            (
                telegram_user.full_name
                or "Pengguna ReceiptBot"
            ),
            selected_plan,
        )

        if PAYMENT_PROVIDER == "DEVELOPMENT":
            keyboard = (
                build_development_confirmation_keyboard(
                    checkout.payment_reference
                )
            )
        else:
            keyboard = build_back_keyboard()

        await query.edit_message_text(
            text=format_checkout_message(
                selected_plan,
                checkout,
            ),
            reply_markup=keyboard,
        )

    except PaymentProviderNotConfiguredError:
        await query.edit_message_text(
            "⚠️ Pembayaran belum tersedia.",
            reply_markup=build_back_keyboard(),
        )

    except PaymentServiceError as error:
        await query.edit_message_text(
            "Checkout gagal dicipta.\n\n"
            f"{error}",
            reply_markup=build_back_keyboard(),
        )

    except Exception as error:
        logger.exception(
            "Pilihan upgrade gagal: %s",
            error,
        )

        await query.edit_message_text(
            "Pilihan pelan gagal diproses.",
            reply_markup=build_back_keyboard(),
        )