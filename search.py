import asyncio
import logging
from datetime import datetime
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from database import (
    get_user_by_telegram_id,
    supabase,
)
from feature_gate import ensure_feature_access
from features import FeatureCode


logger = logging.getLogger(__name__)

MAX_SEARCH_RESULTS = 10
MAX_RECEIPTS_TO_SCAN = 500
MAX_SEARCH_QUERY_LENGTH = 50

MONTH_NAMES = {
    1: "Jan",
    2: "Feb",
    3: "Mac",
    4: "Apr",
    5: "Mei",
    6: "Jun",
    7: "Jul",
    8: "Ogos",
    9: "Sep",
    10: "Okt",
    11: "Nov",
    12: "Dis",
}


def normalize_search_text(
    value: Any,
) -> str:
    """Tukar nilai kepada teks carian yang konsisten."""

    if value is None:
        return ""

    return str(value).strip().casefold()


def format_receipt_date(
    receipt_date: Any,
) -> str:
    """Format tarikh resit kepada paparan ringkas."""

    if not isinstance(
        receipt_date,
        str,
    ):
        return "Tarikh tidak diketahui"

    try:
        parsed_date = datetime.strptime(
            receipt_date,
            "%Y-%m-%d",
        )
    except ValueError:
        return receipt_date

    month_name = MONTH_NAMES[
        parsed_date.month
    ]

    return (
        f"{parsed_date.day} "
        f"{month_name} "
        f"{parsed_date.year}"
    )


def parse_receipt_total(
    raw_total: Any,
) -> float:
    """Tukar jumlah resit kepada float dengan selamat."""

    try:
        return float(raw_total)
    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def receipt_matches_query(
    receipt: dict[str, Any],
    normalized_query: str,
) -> bool:
    """Semak sama ada resit sepadan dengan kata kunci."""

    merchant = normalize_search_text(
        receipt.get("merchant")
    )

    category = normalize_search_text(
        receipt.get("category")
    )

    receipt_date = normalize_search_text(
        receipt.get("receipt_date")
    )

    total = parse_receipt_total(
        receipt.get("total")
    )

    total_variations = {
        normalize_search_text(total),
        normalize_search_text(
            f"{total:.2f}"
        ),
        normalize_search_text(
            f"rm{total:.2f}"
        ),
        normalize_search_text(
            f"rm {total:.2f}"
        ),
    }

    return (
        normalized_query in merchant
        or normalized_query in category
        or normalized_query in receipt_date
        or normalized_query in total_variations
    )


def search_user_receipts(
    telegram_id: int,
    search_query: str,
) -> list[dict[str, Any]]:
    """Cari resit pengguna berdasarkan kata kunci."""

    user = get_user_by_telegram_id(
        telegram_id
    )

    user_id = user.get("id")

    if user_id is None:
        raise RuntimeError(
            "User ID tidak dijumpai."
        )

    normalized_query = normalize_search_text(
        search_query
    )

    response = (
        supabase.table("receipts")
        .select(
            "id,merchant,total,"
            "receipt_date,category,created_at"
        )
        .eq(
            "user_id",
            user_id,
        )
        .order(
            "receipt_date",
            desc=True,
        )
        .order(
            "created_at",
            desc=True,
        )
        .limit(
            MAX_RECEIPTS_TO_SCAN
        )
        .execute()
    )

    receipts = response.data or []

    matching_receipts: list[
        dict[str, Any]
    ] = []

    for receipt in receipts:
        if receipt_matches_query(
            receipt=receipt,
            normalized_query=normalized_query,
        ):
            matching_receipts.append(
                receipt
            )

        if (
            len(matching_receipts)
            >= MAX_SEARCH_RESULTS
        ):
            break

    return matching_receipts


def format_search_results(
    search_query: str,
    receipts: list[dict[str, Any]],
) -> str:
    """Sediakan mesej hasil carian."""

    if not receipts:
        return (
            "🔎 Carian Resit\n\n"
            f"Kata kunci\n{search_query}\n\n"
            "Tiada resit yang sepadan dijumpai.\n\n"
            "Cuba cari menggunakan:\n"
            "• Nama kedai\n"
            "• Kategori\n"
            "• Tarikh, contoh 2026-07-27\n"
            "• Jumlah, contoh 14.00"
        )

    receipt_sections: list[str] = []

    for index, receipt in enumerate(
        receipts,
        start=1,
    ):
        merchant = (
            receipt.get("merchant")
            or "Peniaga tidak diketahui"
        )

        category = (
            receipt.get("category")
            or "Lain-lain"
        )

        receipt_date = format_receipt_date(
            receipt.get("receipt_date")
        )

        total = parse_receipt_total(
            receipt.get("total")
        )

        receipt_sections.append(
            f"{index}. {merchant}\n"
            f"   💰 RM{total:,.2f}\n"
            f"   📅 {receipt_date}\n"
            f"   📂 {category}"
        )

    result_count = len(receipts)

    return (
        "🔎 Hasil Carian Resit\n\n"
        f"Kata kunci\n{search_query}\n\n"
        f"Dijumpai\n{result_count} resit\n\n"
        "──────────────\n\n"
        + "\n\n──────────────\n\n".join(
            receipt_sections
        )
        + "\n\nPaparan maksimum "
        f"{MAX_SEARCH_RESULTS} hasil."
    )


async def search_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Cari rekod resit pengguna."""

    if update.message is None:
        return

    allowed = await ensure_feature_access(
        update=update,
        context=context,
        feature_code=(
            FeatureCode.SEARCH_RECEIPTS
        ),
    )

    if not allowed:
        return

    if not context.args:
        await update.message.reply_text(
            "🔎 Carian Resit\n\n"
            "Gunakan format:\n"
            "/search kata_kunci\n\n"
            "Contoh:\n"
            "/search 99 Speed Mart\n"
            "/search Bahan Mentah\n"
            "/search 2026-07-27\n"
            "/search 14.00"
        )
        return

    search_query = " ".join(
        context.args
    ).strip()

    if not search_query:
        await update.message.reply_text(
            "Masukkan kata kunci carian.\n\n"
            "Contoh:\n"
            "/search 99 Speed Mart"
        )
        return

    if (
        len(search_query)
        > MAX_SEARCH_QUERY_LENGTH
    ):
        await update.message.reply_text(
            "Kata kunci terlalu panjang.\n\n"
            "Gunakan maksimum "
            f"{MAX_SEARCH_QUERY_LENGTH} aksara."
        )
        return

    telegram_user = update.effective_user

    if telegram_user is None:
        await update.message.reply_text(
            "Maklumat pengguna tidak dapat dibaca."
        )
        return

    status_message = await update.message.reply_text(
        "⏳ Mencari resit..."
    )

    try:
        matching_receipts = await asyncio.to_thread(
            search_user_receipts,
            telegram_user.id,
            search_query,
        )

        await status_message.edit_text(
            format_search_results(
                search_query=search_query,
                receipts=matching_receipts,
            )
        )

    except Exception as error:
        logger.exception(
            "Gagal mencari resit. "
            "Telegram ID: %s | Carian: %s | Ralat: %s",
            telegram_user.id,
            search_query,
            error,
        )

        await status_message.edit_text(
            "Carian resit gagal dilakukan.\n\n"
            "Sila cuba semula."
        )