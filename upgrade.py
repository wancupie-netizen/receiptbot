import asyncio
import logging
from decimal import Decimal

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

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

CALLBACK_UPGRADE_PREFIX = "upgrade:"
CALLBACK_UPGRADE_STARTER = "upgrade:STARTER"
CALLBACK_UPGRADE_BUSINESS = "upgrade:BUSINESS"
CALLBACK_UPGRADE_BACK = "upgrade:BACK"


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
        plan_status = "\n\n✅ Pelan semasa anda"
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

    return (
        "🚀 Upgrade ReceiptBot\n\n"
        "Pilih pelan yang sesuai dengan "
        "keperluan anda.\n\n"
        "━━━━━━━━━━━━━━\n\n"
        + "\n\n━━━━━━━━━━━━━━\n\n".join(
            sections
        )
        + "\n\n━━━━━━━━━━━━━━\n\n"
        "Pembayaran dalam talian akan "
        "tersedia tidak lama lagi."
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
                    text="⭐⭐ Upgrade Business — RM19.90",
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


def format_selected_plan_message(
    selected_plan: Plan,
    current_plan: Plan,
) -> str:
    """Sediakan mesej selepas pengguna memilih pelan."""

    if selected_plan.code == current_plan.code:
        return (
            "✅ Anda sudah menggunakan "
            f"pelan {current_plan.name}."
        )

    feature_lines = "\n".join(
        f"✓ {feature}"
        for feature in get_plan_features(
            selected_plan.code
        )
    )

    return (
        f"{get_plan_icon(selected_plan.code)} "
        f"Pelan {selected_plan.name}\n\n"
        f"Harga\n"
        f"{format_price(selected_plan.monthly_price_rm)}\n\n"
        f"Kuota\n"
        f"{selected_plan.monthly_receipt_limit} "
        "resit / bulan\n\n"
        f"{feature_lines}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "Sistem pembayaran sedang disediakan.\n\n"
        "Apabila pembayaran dilancarkan, "
        "butang ini akan membawa anda terus "
        "ke halaman pembayaran yang selamat."
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

    callback_data = query.data or ""

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

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="⬅️ Kembali ke pilihan pelan",
                        callback_data=(
                            CALLBACK_UPGRADE_BACK
                        ),
                    )
                ]
            ]
        )

        await query.edit_message_text(
            text=format_selected_plan_message(
                selected_plan=selected_plan,
                current_plan=subscription.plan,
            ),
            reply_markup=keyboard,
        )

    except Exception as error:
        logger.exception(
            "Gagal memproses pilihan upgrade. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await query.answer(
            "Pilihan pelan gagal diproses.",
            show_alert=True,
        )