from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final

from features import FeatureCode


class PlanCode(StrEnum):
    """Kod rasmi pelan ReceiptBot."""

    FREE = "FREE"
    STARTER = "STARTER"
    BUSINESS = "BUSINESS"


class StorageRetentionType(StrEnum):
    """Jenis tempoh penyimpanan gambar resit."""

    DAYS = "DAYS"
    WHILE_SUBSCRIBED = "WHILE_SUBSCRIBED"


@dataclass(
    frozen=True,
    slots=True,
)
class StorageRetention:
    """Peraturan penyimpanan gambar resit."""

    retention_type: StorageRetentionType
    days: int | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class Plan:
    """Definisi rasmi sesuatu pelan."""

    code: PlanCode
    name: str
    target_user: str
    monthly_price_rm: Decimal
    monthly_receipt_limit: int
    storage_retention: StorageRetention
    features: frozenset[FeatureCode]

    def has_feature(
        self,
        feature_code: FeatureCode,
    ) -> bool:
        """Semak sama ada pelan mempunyai sesuatu ciri."""

        return feature_code in self.features


FREE_PLAN: Final[Plan] = Plan(
    code=PlanCode.FREE,
    name="Free",
    target_user="Tester dan pengguna baharu",
    monthly_price_rm=Decimal("0.00"),
    monthly_receipt_limit=20,
    storage_retention=StorageRetention(
        retention_type=(
            StorageRetentionType.DAYS
        ),
        days=30,
    ),
    features=frozenset(
        {
            FeatureCode.AI_RECEIPT_READING,
            FeatureCode.AI_AUTO_CATEGORY,
            FeatureCode.BASIC_DASHBOARD,
            FeatureCode.MONTHLY_SUMMARY,
            FeatureCode.RECENT_RECEIPTS,
        }
    ),
)


STARTER_PLAN: Final[Plan] = Plan(
    code=PlanCode.STARTER,
    name="Starter",
    target_user="Individu dan seller kecil",
    monthly_price_rm=Decimal("9.90"),
    monthly_receipt_limit=100,
    storage_retention=StorageRetention(
        retention_type=(
            StorageRetentionType.DAYS
        ),
        days=365,
    ),
    features=frozenset(
        {
            FeatureCode.AI_RECEIPT_READING,
            FeatureCode.AI_AUTO_CATEGORY,
            FeatureCode.FULL_DASHBOARD,
            FeatureCode.MONTHLY_SUMMARY,
            FeatureCode.RECENT_RECEIPTS,
            FeatureCode.SEARCH_RECEIPTS,
            FeatureCode.EDIT_SAVED_RECEIPT,
            FeatureCode.DELETE_SAVED_RECEIPT,
            FeatureCode.EXPORT_CSV,
        }
    ),
)


BUSINESS_PLAN: Final[Plan] = Plan(
    code=PlanCode.BUSINESS,
    name="Business",
    target_user="Peniaga dan bisnes kecil",
    monthly_price_rm=Decimal("19.90"),
    monthly_receipt_limit=500,
    storage_retention=StorageRetention(
        retention_type=(
            StorageRetentionType.WHILE_SUBSCRIBED
        ),
        days=None,
    ),
    features=frozenset(
        {
            FeatureCode.AI_RECEIPT_READING,
            FeatureCode.AI_AUTO_CATEGORY,
            FeatureCode.FULL_DASHBOARD,
            FeatureCode.MONTHLY_SUMMARY,
            FeatureCode.RECENT_RECEIPTS,
            FeatureCode.SEARCH_RECEIPTS,
            FeatureCode.EDIT_SAVED_RECEIPT,
            FeatureCode.DELETE_SAVED_RECEIPT,
            FeatureCode.EXPORT_CSV,
            FeatureCode.EXPORT_EXCEL,
            FeatureCode.EXPORT_PDF,
            FeatureCode.CUSTOM_CATEGORIES,
            FeatureCode.INCOME_RECORDS,
            FeatureCode.EXPENSE_RECORDS,
        }
    ),
)


PLANS: Final[
    dict[PlanCode, Plan]
] = {
    PlanCode.FREE: FREE_PLAN,
    PlanCode.STARTER: STARTER_PLAN,
    PlanCode.BUSINESS: BUSINESS_PLAN,
}


DEFAULT_PLAN_CODE: Final[PlanCode] = (
    PlanCode.FREE
)


def get_plan(
    plan_code: PlanCode | str,
) -> Plan:
    """Dapatkan definisi pelan berdasarkan kod."""

    try:
        normalized_code = PlanCode(
            str(plan_code).upper()
        )
    except ValueError as error:
        raise ValueError(
            f"Pelan tidak dikenali: {plan_code}"
        ) from error

    return PLANS[normalized_code]


def get_monthly_receipt_limit(
    plan_code: PlanCode | str,
) -> int:
    """Dapatkan had resit bulanan sesuatu pelan."""

    return get_plan(
        plan_code
    ).monthly_receipt_limit


def plan_has_feature(
    plan_code: PlanCode | str,
    feature_code: FeatureCode,
) -> bool:
    """Semak kebenaran ciri berdasarkan pelan."""

    return get_plan(
        plan_code
    ).has_feature(feature_code)


# Compatibility untuk modul Free Plan sedia ada.
FREE_PLAN_NAME: Final[str] = (
    FREE_PLAN.name
)

FREE_PLAN_MONTHLY_LIMIT: Final[int] = (
    FREE_PLAN.monthly_receipt_limit
)

STARTER_PLAN_NAME: Final[str] = (
    STARTER_PLAN.name
)

STARTER_PLAN_MONTHLY_LIMIT: Final[int] = (
    STARTER_PLAN.monthly_receipt_limit
)

BUSINESS_PLAN_NAME: Final[str] = (
    BUSINESS_PLAN.name
)

BUSINESS_PLAN_MONTHLY_LIMIT: Final[int] = (
    BUSINESS_PLAN.monthly_receipt_limit
)