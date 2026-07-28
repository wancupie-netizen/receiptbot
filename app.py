import logging

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from account import account_command
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
    start,
)
from config import BOT_TOKEN
from dashboard import dashboard_command
from export_csv import export_csv_command
from free_plan import (
    receive_receipt_with_plan_check,
)
from help import help_command
from receipts import receipts_command
from search import search_command
from summary import summary_command
from upgrade import (
    CALLBACK_UPGRADE_PREFIX,
    handle_upgrade_action,
    upgrade_command,
)


logging.basicConfig(
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
    level=logging.INFO,
)


async def setup_bot_commands(
    application: Application,
) -> None:
    """Daftar command yang dipaparkan dalam menu Telegram."""

    commands = [
        BotCommand(
            command="start",
            description="Mulakan ReceiptBot",
        ),
        BotCommand(
            command="dashboard",
            description="Lihat dashboard perbelanjaan",
        ),
        BotCommand(
            command="receipts",
            description="Lihat resit terkini",
        ),
        BotCommand(
            command="search",
            description="Cari rekod resit",
        ),
        BotCommand(
            command="export_csv",
            description="Eksport rekod ke CSV",
        ),
        BotCommand(
            command="summary",
            description="Lihat ringkasan bulan ini",
        ),
        BotCommand(
            command="account",
            description="Lihat maklumat akaun",
        ),
        BotCommand(
            command="upgrade",
            description="Lihat dan pilih pelan",
        ),
        BotCommand(
            command="help",
            description="Lihat panduan penggunaan",
        ),
    ]

    await application.bot.set_my_commands(
        commands
    )


def main() -> None:
    """Jalankan ReceiptBot."""

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(setup_bot_commands)
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
        CommandHandler(
            "search",
            search_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "export_csv",
            export_csv_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "summary",
            summary_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "account",
            account_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "upgrade",
            upgrade_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            receive_receipt_with_plan_check,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            handle_upgrade_action,
            pattern=(
                f"^{CALLBACK_UPGRADE_PREFIX}"
            ),
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