import asyncio
import logging
from dataclasses import dataclass

from telegram import Update
from telegram.ext import ContextTypes

from features import (
    FeatureCode,
    get_feature_name,
)
from plans import (
    PLANS,
    Plan,
    PlanCode,
)
from subscription_service import (
    SubscriptionContext,
    get_subscription_context,
)


logger = logging.getLogger(__name__)


PLAN_PRIORITY = {
    PlanCode.FREE: 0,
    PlanCode.STARTER: 1,
    PlanCode.BUSINESS: 2,
}


@dataclass(
    frozen=True,
    slots=True,
)
class FeatureAccessResult:
    """Keputusan semakan akses sesuatu ciri."""

    allowed: bool

    feature_code: FeatureCode
    feature_name: str

    current_plan_code: PlanCode
    current_plan_name: str

    required_plan_code: PlanCode | None
    required_plan_name: str | None

    message: str


def get_minimum_plan_for_feature(
    feature_code: FeatureCode,
) -> Plan | None:
    """
    Cari pelan paling rendah yang mempunyai sesuatu ciri.

    Add-on tidak dipertimbangkan di sini kerana fungsi ini
    hanya digunakan untuk cadangan naik taraf.
    """

    eligible_plans = [
        plan
        for plan in PLANS.values()
        if plan.has_feature(feature_code)
    ]

    if not eligible_plans:
        return None

    return min(
        eligible_plans,
        key=lambda plan: PLAN_PRIORITY[
            plan.code
        ],
    )


def format_plan_price(
    plan: Plan,
) -> str:
    """Format harga pelan."""

    if plan.monthly_price_rm == 0:
        return "RM0"

    return (
        f"RM{plan.monthly_price_rm:.2f} "
        "/ bulan"
    )


def build_access_allowed_message(
    feature_name: str,
    subscription: SubscriptionContext,
) -> str:
    """Sediakan mesej akses dibenarkan."""

    return (
        f"✅ Akses dibenarkan\n\n"
        f"Ciri: {feature_name}\n"
        f"Pelan: {subscription.plan.name}"
    )


def build_access_denied_message(
    feature_name: str,
    subscription: SubscriptionContext,
    required_plan: Plan | None,
) -> str:
    """Sediakan mesej akses tidak dibenarkan."""

    if required_plan is None:
        return (
            "🔒 Ciri Belum Tersedia\n\n"
            f"{feature_name} belum tersedia "
            "untuk digunakan buat masa ini."
        )

    return (
        "🔒 Ciri Tidak Termasuk Dalam Pelan Anda\n\n"
        f"Ciri\n{feature_name}\n\n"
        f"Pelan Semasa\n"
        f"{subscription.plan.name}\n\n"
        f"Pelan Diperlukan\n"
        f"{required_plan.name}\n"
        f"{format_plan_price(required_plan)}\n\n"
        "Naik taraf pelan untuk menggunakan "
        "ciri ini."
    )


def check_feature_access(
    telegram_id: int,
    feature_code: FeatureCode,
) -> FeatureAccessResult:
    """Semak akses pengguna kepada sesuatu ciri."""

    subscription = get_subscription_context(
        telegram_id
    )

    feature_name = get_feature_name(
        feature_code
    )

    allowed = (
        feature_code
        in subscription.features
    )

    required_plan = None

    if not allowed:
        required_plan = (
            get_minimum_plan_for_feature(
                feature_code
            )
        )

    if allowed:
        message = build_access_allowed_message(
            feature_name=feature_name,
            subscription=subscription,
        )
    else:
        message = build_access_denied_message(
            feature_name=feature_name,
            subscription=subscription,
            required_plan=required_plan,
        )

    return FeatureAccessResult(
        allowed=allowed,
        feature_code=feature_code,
        feature_name=feature_name,
        current_plan_code=(
            subscription.plan_code
        ),
        current_plan_name=(
            subscription.plan.name
        ),
        required_plan_code=(
            required_plan.code
            if required_plan is not None
            else None
        ),
        required_plan_name=(
            required_plan.name
            if required_plan is not None
            else None
        ),
        message=message,
    )


def require_feature_access(
    telegram_id: int,
    feature_code: FeatureCode,
) -> None:
    """
    Pastikan pengguna mempunyai akses.

    Raises:
        PermissionError jika akses tidak dibenarkan.
    """

    result = check_feature_access(
        telegram_id=telegram_id,
        feature_code=feature_code,
    )

    if not result.allowed:
        raise PermissionError(
            result.message
        )


async def check_feature_access_async(
    telegram_id: int,
    feature_code: FeatureCode,
) -> FeatureAccessResult:
    """Versi async untuk handler Telegram."""

    return await asyncio.to_thread(
        check_feature_access,
        telegram_id,
        feature_code,
    )


async def ensure_feature_access(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    feature_code: FeatureCode,
) -> bool:
    """
    Semak akses dalam handler Telegram.

    Jika akses ditolak, mesej upgrade akan dihantar
    secara automatik.

    Returns:
        True jika dibenarkan.
        False jika ditolak atau pengguna tidak dapat dibaca.
    """

    telegram_user = update.effective_user

    if telegram_user is None:
        if update.message is not None:
            await update.message.reply_text(
                "Maklumat pengguna tidak dapat dibaca."
            )

        return False

    try:
        result = await check_feature_access_async(
            telegram_id=telegram_user.id,
            feature_code=feature_code,
        )

    except Exception as error:
        logger.exception(
            "Gagal menyemak akses ciri. "
            "Telegram ID: %s | Ciri: %s | Ralat: %s",
            telegram_user.id,
            feature_code.value,
            error,
        )

        if update.message is not None:
            await update.message.reply_text(
                "ReceiptBot gagal menyemak "
                "akses pelan anda.\n\n"
                "Sila cuba semula."
            )

        return False

    if result.allowed:
        return True

    if update.message is not None:
        await update.message.reply_text(
            result.message
        )

    elif update.callback_query is not None:
        await update.callback_query.answer(
            "Ciri ini tidak termasuk "
            "dalam pelan anda.",
            show_alert=True,
        )

    return False