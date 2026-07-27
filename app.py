import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot import (
    CALLBACK_CANCEL,
    CALLBACK_CATEGORY_PREFIX,
    CALLBACK_CONFIRM,
    CALLBACK_EDIT,
    CALLBACK_EDIT_BACK,
    CALLBACK_EDIT_CATEGORY,
    CALLBACK_EDIT_DATE,
    CALLBACK_EDIT_MERCHANT,
    CALLBACK_EDIT_TOTAL,
    handle_receipt_action,
    handle_text_message,
    receive_receipt,
    start,
)
from config import BOT_TOKEN
from dashboard import dashboard_command
from receipts import receipts_command


logging.basicConfig(
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
    level=logging.INFO,
)


def main() -> None:
    """Jalankan ReceiptBot."""

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "dashboard",
            dashboard_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "receipts",
            receipts_command,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            receive_receipt,
        )
    )

    callback_pattern = (
        f"^("
        f"{CALLBACK_CONFIRM}|"
        f"{CALLBACK_EDIT}|"
        f"{CALLBACK_CANCEL}|"
        f"{CALLBACK_EDIT_MERCHANT}|"
        f"{CALLBACK_EDIT_DATE}|"
        f"{CALLBACK_EDIT_TOTAL}|"
        f"{CALLBACK_EDIT_CATEGORY}|"
        f"{CALLBACK_EDIT_BACK}|"
        f"{CALLBACK_CATEGORY_PREFIX}.*"
        f")$"
    )

    application.add_handler(
        CallbackQueryHandler(
            handle_receipt_action,
            pattern=callback_pattern,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text_message,
        )
    )

    print("ReceiptBot sedang berjalan...")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()