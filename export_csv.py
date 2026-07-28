import asyncio
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

from database import (
    get_user_by_telegram_id,
    supabase,
)
from feature_gate import ensure_feature_access
from features import FeatureCode


logger = logging.getLogger(__name__)

MALAYSIA_TIMEZONE = ZoneInfo(
    "Asia/Kuching"
)

EXPORT_FOLDER = Path(
    "temp_exports"
)

EXPORT_FOLDER.mkdir(
    exist_ok=True
)

DATABASE_PAGE_SIZE = 500


def parse_total(
    raw_total: Any,
) -> float:
    """Tukar jumlah resit kepada nombor dengan selamat."""

    try:
        return float(raw_total)
    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def format_created_at(
    created_at: Any,
) -> str:
    """Format waktu rekod disimpan."""

    if not isinstance(
        created_at,
        str,
    ):
        return ""

    normalized_value = created_at.replace(
        "Z",
        "+00:00",
    )

    try:
        parsed_datetime = datetime.fromisoformat(
            normalized_value
        )
    except ValueError:
        return created_at

    if parsed_datetime.tzinfo is None:
        return parsed_datetime.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    local_datetime = parsed_datetime.astimezone(
        MALAYSIA_TIMEZONE
    )

    return local_datetime.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def get_all_user_receipts(
    telegram_id: int,
) -> list[dict[str, Any]]:
    """Dapatkan semua rekod resit pengguna secara berhalaman."""

    user = get_user_by_telegram_id(
        telegram_id
    )

    user_id = user.get(
        "id"
    )

    if user_id is None:
        raise RuntimeError(
            "User ID tidak dijumpai."
        )

    receipts: list[
        dict[str, Any]
    ] = []

    start_index = 0

    while True:
        end_index = (
            start_index
            + DATABASE_PAGE_SIZE
            - 1
        )

        response = (
            supabase.table("receipts")
            .select(
                "id,merchant,total,"
                "receipt_date,category,"
                "created_at,image_url"
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
            .range(
                start_index,
                end_index,
            )
            .execute()
        )

        page_receipts = (
            response.data or []
        )

        receipts.extend(
            page_receipts
        )

        if (
            len(page_receipts)
            < DATABASE_PAGE_SIZE
        ):
            break

        start_index += DATABASE_PAGE_SIZE

    return receipts


def create_csv_export(
    telegram_id: int,
    receipts: list[dict[str, Any]],
) -> Path:
    """Hasilkan fail CSV resit pengguna."""

    timestamp = datetime.now(
        MALAYSIA_TIMEZONE
    ).strftime(
        "%Y%m%d_%H%M%S"
    )

    filename = (
        f"receiptbot_{telegram_id}_"
        f"{timestamp}_{uuid4().hex[:8]}.csv"
    )

    file_path = (
        EXPORT_FOLDER
        / filename
    )

    with file_path.open(
        mode="w",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:
        writer = csv.writer(
            csv_file
        )

        writer.writerow(
            [
                "No.",
                "Tarikh Resit",
                "Nama Kedai",
                "Kategori",
                "Jumlah (RM)",
                "Tarikh Disimpan",
                "ID Resit",
            ]
        )

        for index, receipt in enumerate(
            receipts,
            start=1,
        ):
            merchant = (
                receipt.get("merchant")
                or "Tidak diketahui"
            )

            category = (
                receipt.get("category")
                or "Lain-lain"
            )

            receipt_date = (
                receipt.get("receipt_date")
                or ""
            )

            total = parse_total(
                receipt.get("total")
            )

            created_at = format_created_at(
                receipt.get("created_at")
            )

            receipt_id = (
                receipt.get("id")
                or ""
            )

            writer.writerow(
                [
                    index,
                    receipt_date,
                    merchant,
                    category,
                    f"{total:.2f}",
                    created_at,
                    receipt_id,
                ]
            )

    return file_path


def build_export_caption(
    receipt_count: int,
) -> str:
    """Sediakan caption fail eksport."""

    return (
        "📄 Export CSV ReceiptBot\n\n"
        f"Jumlah rekod: {receipt_count}\n\n"
        "Fail ini mengandungi rekod resit "
        "yang disimpan dalam akaun anda."
    )


async def export_csv_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Eksport semua rekod resit pengguna ke CSV."""

    if update.message is None:
        return

    allowed = await ensure_feature_access(
        update=update,
        context=context,
        feature_code=(
            FeatureCode.EXPORT_CSV
        ),
    )

    if not allowed:
        return

    telegram_user = update.effective_user

    if telegram_user is None:
        await update.message.reply_text(
            "Maklumat pengguna tidak dapat dibaca."
        )
        return

    status_message = await update.message.reply_text(
        "⏳ Menyediakan fail CSV..."
    )

    export_path: Path | None = None

    try:
        receipts = await asyncio.to_thread(
            get_all_user_receipts,
            telegram_user.id,
        )

        if not receipts:
            await status_message.edit_text(
                "📄 Export CSV\n\n"
                "Belum ada rekod resit untuk dieksport."
            )
            return

        export_path = await asyncio.to_thread(
            create_csv_export,
            telegram_user.id,
            receipts,
        )

        await status_message.edit_text(
            "⏳ Menghantar fail CSV..."
        )

        with export_path.open(
            "rb"
        ) as csv_file:
            await update.message.reply_document(
                document=csv_file,
                filename=(
                    f"receiptbot_export_"
                    f"{datetime.now(MALAYSIA_TIMEZONE).strftime('%Y-%m-%d')}"
                    ".csv"
                ),
                caption=build_export_caption(
                    len(receipts)
                ),
            )

        await status_message.delete()

        logger.info(
            "Export CSV berjaya. "
            "Telegram ID: %s | Jumlah rekod: %s",
            telegram_user.id,
            len(receipts),
        )

    except Exception as error:
        logger.exception(
            "Export CSV gagal. "
            "Telegram ID: %s | Ralat: %s",
            telegram_user.id,
            error,
        )

        await status_message.edit_text(
            "Export CSV gagal dilakukan.\n\n"
            "Sila cuba semula."
        )

    finally:
        if (
            export_path is not None
            and export_path.exists()
        ):
            try:
                export_path.unlink()

                logger.info(
                    "Fail CSV sementara dipadam: %s",
                    export_path,
                )

            except OSError as error:
                logger.warning(
                    "Fail CSV sementara gagal dipadam. "
                    "Fail: %s | Ralat: %s",
                    export_path,
                    error,
                )