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
    CALLBACK_CONFIRM,
    CALLBACK_EDIT,
    handle_receipt_action,
    handle_text_message,
    receive_receipt,
    start,
)
from config import BOT_TOKEN


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
        MessageHandler(
            filters.PHOTO,
            receive_receipt,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            handle_receipt_action,
            pattern=(
                f"^({CALLBACK_CONFIRM}|"
                f"{CALLBACK_EDIT}|"
                f"{CALLBACK_CANCEL})$"
            ),
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