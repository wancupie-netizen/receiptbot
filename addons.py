from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final

from features import FeatureCode
from plans import PlanCode


class AddOnCode(StrEnum):
    """Kod rasmi add-on ReceiptBot."""

    EXTRA_100_RECEIPTS = "EXTRA_100_RECEIPTS"
    EXTRA_500_RECEIPTS = "EXTRA_500_RECEIPTS"

    EXTRA_STAFF = "EXTRA_STAFF"
    ACCOUNTANT_REPORT = "ACCOUNTANT_REPORT"

    IMPORT_CSV = "IMPORT_CSV"
    IMPORT_LEGACY_DATA = "IMPORT_LEGACY_DATA"
    BUSINESS_CATEGORY_SETUP = (
        "BUSINESS_CATEGORY_SETUP"
    )

    WHITE_LABEL = "WHITE_LABEL"


class BillingType(StrEnum):
    """Jenis bayaran add-on."""

    ONE_TIME = "ONE_TIME"
    MONTHLY = "MONTHLY"


@dataclass(
    frozen=True,
    slots=True,
)
class AddOn:
    """Definisi rasmi sesuatu add-on."""

    code: AddOnCode
    name: str
    description: str
    price_rm: Decimal
    billing_type: BillingType

    allowed_plans: frozenset[PlanCode]

    extra_monthly_receipts: int = 0
    extra_staff: int = 0

    granted_features: frozenset[
        FeatureCode
    ] = frozenset()

    is_active: bool = False


EXTRA_100_RECEIPTS: Final[AddOn] = AddOn(
    code=AddOnCode.EXTRA_100_RECEIPTS,
    name="Tambahan 100 Resit",
    description=(
        "Tambah 100 resit kepada kuota "
        "bulan semasa."
    ),
    price_rm=Decimal("5.00"),
    billing_type=BillingType.ONE_TIME,
    allowed_plans=frozenset(
        {
            PlanCode.FREE,
            PlanCode.STARTER,
            PlanCode.BUSINESS,
        }
    ),
    extra_monthly_receipts=100,
    is_active=False,
)


EXTRA_500_RECEIPTS: Final[AddOn] = AddOn(
    code=AddOnCode.EXTRA_500_RECEIPTS,
    name="Tambahan 500 Resit",
    description=(
        "Tambah 500 resit kepada kuota "
        "bulan semasa."
    ),
    price_rm=Decimal("15.00"),
    billing_type=BillingType.ONE_TIME,
    allowed_plans=frozenset(
        {
            PlanCode.STARTER,
            PlanCode.BUSINESS,
        }
    ),
    extra_monthly_receipts=500,
    is_active=False,
)


EXTRA_STAFF: Final[AddOn] = AddOn(
    code=AddOnCode.EXTRA_STAFF,
    name="Tambahan Seorang Staf",
    description=(
        "Tambah satu akaun staf kepada "
        "akaun Business."
    ),
    price_rm=Decimal("5.00"),
    billing_type=BillingType.MONTHLY,
    allowed_plans=frozenset(
        {
            PlanCode.BUSINESS,
        }
    ),
    extra_staff=1,
    granted_features=frozenset(
        {
            FeatureCode.STAFF_ACCOUNTS,
        }
    ),
    is_active=False,
)


ACCOUNTANT_REPORT: Final[AddOn] = AddOn(
    code=AddOnCode.ACCOUNTANT_REPORT,
    name="Laporan Akauntan",
    description=(
        "Laporan tambahan yang disusun "
        "untuk semakan akauntan."
    ),
    price_rm=Decimal("10.00"),
    billing_type=BillingType.MONTHLY,
    allowed_plans=frozenset(
        {
            PlanCode.STARTER,
            PlanCode.BUSINESS,
        }
    ),
    granted_features=frozenset(
        {
            FeatureCode.ACCOUNTANT_REPORT,
        }
    ),
    is_active=False,
)


IMPORT_CSV: Final[AddOn] = AddOn(
    code=AddOnCode.IMPORT_CSV,
    name="Import Rekod CSV",
    description=(
        "Import rekod lama daripada "
        "fail CSV."
    ),
    price_rm=Decimal("20.00"),
    billing_type=BillingType.ONE_TIME,
    allowed_plans=frozenset(
        {
            PlanCode.STARTER,
            PlanCode.BUSINESS,
        }
    ),
    is_active=False,
)


IMPORT_LEGACY_DATA: Final[AddOn] = AddOn(
    code=AddOnCode.IMPORT_LEGACY_DATA,
    name="Import Sistem Lama",
    description=(
        "Khidmat import rekod daripada "
        "sistem atau format lama."
    ),
    price_rm=Decimal("50.00"),
    billing_type=BillingType.ONE_TIME,
    allowed_plans=frozenset(
        {
            PlanCode.BUSINESS,
        }
    ),
    is_active=False,
)


BUSINESS_CATEGORY_SETUP: Final[AddOn] = AddOn(
    code=AddOnCode.BUSINESS_CATEGORY_SETUP,
    name="Setup Kategori Bisnes",
    description=(
        "Setup kategori, projek dan pusat "
        "kos mengikut keperluan bisnes."
    ),
    price_rm=Decimal("49.00"),
    billing_type=BillingType.ONE_TIME,
    allowed_plans=frozenset(
        {
            PlanCode.BUSINESS,
        }
    ),
    is_active=False,
)


WHITE_LABEL: Final[AddOn] = AddOn(
    code=AddOnCode.WHITE_LABEL,
    name="White-label",
    description=(
        "ReceiptBot menggunakan identiti "
        "jenama akauntan atau agensi."
    ),
    price_rm=Decimal("99.00"),
    billing_type=BillingType.MONTHLY,
    allowed_plans=frozenset(
        {
            PlanCode.BUSINESS,
        }
    ),
    granted_features=frozenset(
        {
            FeatureCode.WHITE_LABEL,
        }
    ),
    is_active=False,
)


ADDONS: Final[
    dict[AddOnCode, AddOn]
] = {
    AddOnCode.EXTRA_100_RECEIPTS:
        EXTRA_100_RECEIPTS,

    AddOnCode.EXTRA_500_RECEIPTS:
        EXTRA_500_RECEIPTS,

    AddOnCode.EXTRA_STAFF:
        EXTRA_STAFF,

    AddOnCode.ACCOUNTANT_REPORT:
        ACCOUNTANT_REPORT,

    AddOnCode.IMPORT_CSV:
        IMPORT_CSV,

    AddOnCode.IMPORT_LEGACY_DATA:
        IMPORT_LEGACY_DATA,

    AddOnCode.BUSINESS_CATEGORY_SETUP:
        BUSINESS_CATEGORY_SETUP,

    AddOnCode.WHITE_LABEL:
        WHITE_LABEL,
}


def get_addon(
    addon_code: AddOnCode | str,
) -> AddOn:
    """Dapatkan definisi add-on berdasarkan kod."""

    try:
        normalized_code = AddOnCode(
            str(addon_code).upper()
        )
    except ValueError as error:
        raise ValueError(
            f"Add-on tidak dikenali: {addon_code}"
        ) from error

    return ADDONS[normalized_code]


def is_addon_allowed_for_plan(
    addon_code: AddOnCode | str,
    plan_code: PlanCode | str,
) -> bool:
    """Semak sama ada pelan dibenarkan membeli add-on."""

    addon = get_addon(
        addon_code
    )

    normalized_plan = PlanCode(
        str(plan_code).upper()
    )

    return normalized_plan in addon.allowed_plans