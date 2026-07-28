from enum import StrEnum
from typing import Final


class FeatureCode(StrEnum):
    """Kod rasmi semua ciri ReceiptBot."""

    AI_RECEIPT_READING = "AI_RECEIPT_READING"
    AI_AUTO_CATEGORY = "AI_AUTO_CATEGORY"

    BASIC_DASHBOARD = "BASIC_DASHBOARD"
    FULL_DASHBOARD = "FULL_DASHBOARD"
    MONTHLY_SUMMARY = "MONTHLY_SUMMARY"
    RECENT_RECEIPTS = "RECENT_RECEIPTS"

    SEARCH_RECEIPTS = "SEARCH_RECEIPTS"
    EDIT_SAVED_RECEIPT = "EDIT_SAVED_RECEIPT"
    DELETE_SAVED_RECEIPT = "DELETE_SAVED_RECEIPT"

    EXPORT_CSV = "EXPORT_CSV"
    EXPORT_EXCEL = "EXPORT_EXCEL"
    EXPORT_PDF = "EXPORT_PDF"

    CUSTOM_CATEGORIES = "CUSTOM_CATEGORIES"
    INCOME_RECORDS = "INCOME_RECORDS"
    EXPENSE_RECORDS = "EXPENSE_RECORDS"

    STAFF_ACCOUNTS = "STAFF_ACCOUNTS"
    ACCOUNTANT_REPORT = "ACCOUNTANT_REPORT"
    WHITE_LABEL = "WHITE_LABEL"


FEATURE_NAMES: Final[
    dict[FeatureCode, str]
] = {
    FeatureCode.AI_RECEIPT_READING:
        "AI membaca resit",

    FeatureCode.AI_AUTO_CATEGORY:
        "AI kategori automatik",

    FeatureCode.BASIC_DASHBOARD:
        "Dashboard asas",

    FeatureCode.FULL_DASHBOARD:
        "Dashboard penuh",

    FeatureCode.MONTHLY_SUMMARY:
        "Ringkasan bulanan",

    FeatureCode.RECENT_RECEIPTS:
        "Resit terkini",

    FeatureCode.SEARCH_RECEIPTS:
        "Carian resit",

    FeatureCode.EDIT_SAVED_RECEIPT:
        "Edit rekod selepas disimpan",

    FeatureCode.DELETE_SAVED_RECEIPT:
        "Padam rekod",

    FeatureCode.EXPORT_CSV:
        "Eksport CSV",

    FeatureCode.EXPORT_EXCEL:
        "Eksport Excel",

    FeatureCode.EXPORT_PDF:
        "Eksport PDF",

    FeatureCode.CUSTOM_CATEGORIES:
        "Kategori tersuai",

    FeatureCode.INCOME_RECORDS:
        "Rekod pendapatan",

    FeatureCode.EXPENSE_RECORDS:
        "Rekod perbelanjaan",

    FeatureCode.STAFF_ACCOUNTS:
        "Akaun staf tambahan",

    FeatureCode.ACCOUNTANT_REPORT:
        "Laporan khas akauntan",

    FeatureCode.WHITE_LABEL:
        "White-label",
}


def get_feature_name(
    feature_code: FeatureCode,
) -> str:
    """Dapatkan nama paparan sesuatu ciri."""

    return FEATURE_NAMES.get(
        feature_code,
        feature_code.value,
    )