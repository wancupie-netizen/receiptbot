from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from addons import (
    AddOn,
    AddOnCode,
    BillingType,
    get_addon,
)
from database import (
    get_user_by_telegram_id,
    supabase,
)
from features import FeatureCode
from plans import (
    DEFAULT_PLAN_CODE,
    Plan,
    PlanCode,
    StorageRetention,
    get_plan,
)


MALAYSIA_TIMEZONE = ZoneInfo(
    "Asia/Kuching"
)


@dataclass(
    frozen=True,
    slots=True,
)
class ActiveAddOn:
    """Maklumat add-on aktif milik pengguna."""

    record_id: str
    code: AddOnCode
    addon: AddOn
    quantity: int
    starts_at: datetime
    expires_at: datetime | None


@dataclass(
    frozen=True,
    slots=True,
)
class SubscriptionContext:
    """Keputusan lengkap langganan seseorang pengguna."""

    subscription_id: str
    user_id: int
    telegram_id: int

    plan_code: PlanCode
    plan: Plan
    status: str

    starts_at: datetime
    expires_at: datetime | None

    active_addons: tuple[ActiveAddOn, ...]

    monthly_receipt_limit: int
    features: frozenset[FeatureCode]

    is_fallback_free: bool = False


def utc_now() -> datetime:
    """Dapatkan waktu UTC semasa."""

    return datetime.now(timezone.utc)


def parse_database_datetime(
    value: Any,
) -> datetime | None:
    """Tukar nilai timestamptz Supabase kepada datetime."""

    if not isinstance(
        value,
        str,
    ):
        return None

    normalized_value = value.replace(
        "Z",
        "+00:00",
    )

    try:
        parsed_value = datetime.fromisoformat(
            normalized_value
        )
    except ValueError:
        return None

    if parsed_value.tzinfo is None:
        return parsed_value.replace(
            tzinfo=timezone.utc
        )

    return parsed_value.astimezone(
        timezone.utc
    )


def is_time_window_active(
    starts_at: datetime,
    expires_at: datetime | None,
    now: datetime,
) -> bool:
    """Semak sama ada rekod masih berada dalam tempoh aktif."""

    if starts_at > now:
        return False

    if (
        expires_at is not None
        and expires_at <= now
    ):
        return False

    return True


def mark_subscription_expired(
    subscription_id: str,
) -> None:
    """Tandakan langganan tamat dalam database."""

    supabase.table(
        "subscriptions"
    ).update(
        {
            "status": "EXPIRED",
        }
    ).eq(
        "id",
        subscription_id,
    ).execute()


def mark_addon_expired(
    addon_record_id: str,
) -> None:
    """Tandakan add-on tamat dalam database."""

    supabase.table(
        "subscription_addons"
    ).update(
        {
            "status": "EXPIRED",
        }
    ).eq(
        "id",
        addon_record_id,
    ).execute()


def get_active_subscription_record(
    user_id: int,
) -> dict[str, Any] | None:
    """Dapatkan rekod langganan ACTIVE pengguna."""

    response = (
        supabase.table("subscriptions")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "ACTIVE")
        .order(
            "created_at",
            desc=True,
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]


def create_free_subscription(
    user_id: int,
    starts_at: datetime | None = None,
) -> dict[str, Any]:
    """Cipta langganan Free aktif untuk pengguna."""

    effective_start = (
        starts_at
        or utc_now()
    )

    response = (
        supabase.table("subscriptions")
        .insert(
            {
                "user_id": user_id,
                "plan_code": (
                    DEFAULT_PLAN_CODE.value
                ),
                "status": "ACTIVE",
                "starts_at": (
                    effective_start.isoformat()
                ),
                "expires_at": None,
                "price_rm": 0,
                "metadata": {
                    "source": "system_fallback",
                },
            }
        )
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Langganan Free gagal dicipta."
        )

    return response.data[0]


def ensure_active_subscription_record(
    user_id: int,
    now: datetime,
) -> tuple[
    dict[str, Any],
    bool,
]:
    """
    Pastikan pengguna mempunyai langganan aktif.

    Returns:
        tuple[subscription_record, is_fallback_free]
    """

    subscription = get_active_subscription_record(
        user_id
    )

    if subscription is None:
        return (
            create_free_subscription(
                user_id=user_id,
                starts_at=now,
            ),
            True,
        )

    subscription_id = subscription.get(
        "id"
    )

    starts_at = parse_database_datetime(
        subscription.get("starts_at")
    )

    expires_at = parse_database_datetime(
        subscription.get("expires_at")
    )

    if (
        subscription_id is None
        or starts_at is None
    ):
        raise RuntimeError(
            "Rekod langganan tidak lengkap."
        )

    if is_time_window_active(
        starts_at=starts_at,
        expires_at=expires_at,
        now=now,
    ):
        return subscription, False

    mark_subscription_expired(
        str(subscription_id)
    )

    free_subscription = create_free_subscription(
        user_id=user_id,
        starts_at=now,
    )

    return free_subscription, True


def get_active_addon_records(
    subscription_id: str,
) -> list[dict[str, Any]]:
    """Dapatkan add-on berstatus ACTIVE."""

    response = (
        supabase.table("subscription_addons")
        .select("*")
        .eq(
            "subscription_id",
            subscription_id,
        )
        .eq(
            "status",
            "ACTIVE",
        )
        .order(
            "created_at",
            desc=False,
        )
        .execute()
    )

    return response.data or []


def is_receipt_pack_effective_this_month(
    addon: AddOn,
    starts_at: datetime,
    now: datetime,
) -> bool:
    """
    Semak add-on kuota sekali bayar untuk bulan semasa.

    Receipt pack ONE_TIME hanya menambah kuota pada bulan
    ia dibeli. Ini mengelakkan kuota tambahan dibawa secara
    kekal ke bulan seterusnya.
    """

    if addon.extra_monthly_receipts <= 0:
        return True

    if addon.billing_type != BillingType.ONE_TIME:
        return True

    local_start = starts_at.astimezone(
        MALAYSIA_TIMEZONE
    )

    local_now = now.astimezone(
        MALAYSIA_TIMEZONE
    )

    return (
        local_start.year == local_now.year
        and local_start.month == local_now.month
    )


def resolve_active_addons(
    subscription_id: str,
    now: datetime,
) -> tuple[ActiveAddOn, ...]:
    """Sahkan dan bina senarai add-on aktif."""

    records = get_active_addon_records(
        subscription_id
    )

    active_addons: list[ActiveAddOn] = []

    for record in records:
        record_id = record.get("id")
        raw_code = record.get("addon_code")

        starts_at = parse_database_datetime(
            record.get("starts_at")
        )

        expires_at = parse_database_datetime(
            record.get("expires_at")
        )

        if (
            record_id is None
            or raw_code is None
            or starts_at is None
        ):
            continue

        try:
            addon = get_addon(
                str(raw_code)
            )
        except ValueError:
            continue

        if not is_time_window_active(
            starts_at=starts_at,
            expires_at=expires_at,
            now=now,
        ):
            mark_addon_expired(
                str(record_id)
            )
            continue

        if not is_receipt_pack_effective_this_month(
            addon=addon,
            starts_at=starts_at,
            now=now,
        ):
            continue

        raw_quantity = record.get(
            "quantity",
            1,
        )

        try:
            quantity = max(
                int(raw_quantity),
                1,
            )
        except (
            TypeError,
            ValueError,
        ):
            quantity = 1

        active_addons.append(
            ActiveAddOn(
                record_id=str(record_id),
                code=addon.code,
                addon=addon,
                quantity=quantity,
                starts_at=starts_at,
                expires_at=expires_at,
            )
        )

    return tuple(active_addons)


def calculate_monthly_receipt_limit(
    plan: Plan,
    active_addons: tuple[
        ActiveAddOn,
        ...,
    ],
) -> int:
    """Kira had pelan termasuk add-on resit."""

    receipt_limit = (
        plan.monthly_receipt_limit
    )

    for active_addon in active_addons:
        receipt_limit += (
            active_addon.addon
            .extra_monthly_receipts
            * active_addon.quantity
        )

    return receipt_limit


def calculate_features(
    plan: Plan,
    active_addons: tuple[
        ActiveAddOn,
        ...,
    ],
) -> frozenset[FeatureCode]:
    """Gabungkan ciri pelan dengan ciri add-on."""

    features = set(
        plan.features
    )

    for active_addon in active_addons:
        features.update(
            active_addon.addon
            .granted_features
        )

    return frozenset(features)


def get_subscription_context(
    telegram_id: int,
    now: datetime | None = None,
) -> SubscriptionContext:
    """Dapatkan keputusan lengkap langganan pengguna."""

    effective_now = (
        now
        or utc_now()
    )

    if effective_now.tzinfo is None:
        effective_now = effective_now.replace(
            tzinfo=timezone.utc
        )
    else:
        effective_now = (
            effective_now.astimezone(
                timezone.utc
            )
        )

    user = get_user_by_telegram_id(
        telegram_id
    )

    user_id = user.get("id")

    if user_id is None:
        raise RuntimeError(
            "User ID tidak dijumpai."
        )

    subscription, is_fallback_free = (
        ensure_active_subscription_record(
            user_id=int(user_id),
            now=effective_now,
        )
    )

    subscription_id = subscription.get(
        "id"
    )

    raw_plan_code = subscription.get(
        "plan_code",
        DEFAULT_PLAN_CODE.value,
    )

    starts_at = parse_database_datetime(
        subscription.get("starts_at")
    )

    expires_at = parse_database_datetime(
        subscription.get("expires_at")
    )

    if (
        subscription_id is None
        or starts_at is None
    ):
        raise RuntimeError(
            "Maklumat langganan tidak lengkap."
        )

    try:
        plan_code = PlanCode(
            str(raw_plan_code).upper()
        )
    except ValueError:
        plan_code = DEFAULT_PLAN_CODE
        is_fallback_free = True

    plan = get_plan(
        plan_code
    )

    active_addons = resolve_active_addons(
        subscription_id=str(
            subscription_id
        ),
        now=effective_now,
    )

    monthly_receipt_limit = (
        calculate_monthly_receipt_limit(
            plan=plan,
            active_addons=active_addons,
        )
    )

    features = calculate_features(
        plan=plan,
        active_addons=active_addons,
    )

    return SubscriptionContext(
        subscription_id=str(
            subscription_id
        ),
        user_id=int(user_id),
        telegram_id=telegram_id,
        plan_code=plan_code,
        plan=plan,
        status=str(
            subscription.get(
                "status",
                "ACTIVE",
            )
        ),
        starts_at=starts_at,
        expires_at=expires_at,
        active_addons=active_addons,
        monthly_receipt_limit=(
            monthly_receipt_limit
        ),
        features=features,
        is_fallback_free=(
            is_fallback_free
        ),
    )


def get_user_plan(
    telegram_id: int,
) -> Plan:
    """Dapatkan definisi pelan aktif pengguna."""

    return get_subscription_context(
        telegram_id
    ).plan


def get_user_plan_code(
    telegram_id: int,
) -> PlanCode:
    """Dapatkan kod pelan aktif pengguna."""

    return get_subscription_context(
        telegram_id
    ).plan_code


def get_user_monthly_receipt_limit(
    telegram_id: int,
) -> int:
    """Dapatkan had resit termasuk add-on."""

    return get_subscription_context(
        telegram_id
    ).monthly_receipt_limit


def get_user_features(
    telegram_id: int,
) -> frozenset[FeatureCode]:
    """Dapatkan semua ciri yang dimiliki pengguna."""

    return get_subscription_context(
        telegram_id
    ).features


def user_has_feature(
    telegram_id: int,
    feature_code: FeatureCode,
) -> bool:
    """Semak sama ada pengguna dibenarkan menggunakan ciri."""

    return (
        feature_code
        in get_user_features(
            telegram_id
        )
    )


def get_user_storage_retention(
    telegram_id: int,
) -> StorageRetention:
    """Dapatkan polisi penyimpanan pelan pengguna."""

    return get_subscription_context(
        telegram_id
    ).plan.storage_retention


def get_user_active_addons(
    telegram_id: int,
) -> tuple[ActiveAddOn, ...]:
    """Dapatkan semua add-on aktif pengguna."""

    return get_subscription_context(
        telegram_id
    ).active_addons


def is_user_subscription_active(
    telegram_id: int,
) -> bool:
    """Semak sama ada pengguna mempunyai konteks aktif."""

    context = get_subscription_context(
        telegram_id
    )

    return context.status == "ACTIVE"