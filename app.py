import logging

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from account import account_command
from bayarcash_checkout import (
    CALLBACK_BAYARCASH_CONFIRM_PREFIX,
    handle_bayarcash_checkout_action,
)
from billing_profile import (
    BILLING_CONFIRM,
    BILLING_EMAIL,
    BILLING_PHONE,
    billing_command,
    cancel_billing_command,
    handle_billing_confirmation,
    receive_billing_contact,
    receive_billing_email,
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
    start,
)
from config import (
    BOT_TOKEN,
    PAYMENT_PROVIDER,
)
from dashboard import dashboard_command
from development_payment import (
    CALLBACK_DEVELOPMENT_PAYMENT_PREFIX,
    handle_development_payment_action,
)
from export_csv import export_csv_command
from free_plan import (
    receive_receipt_with_plan_check,
)
from help import help_command
from payment_service import (
    DevelopmentPaymentGateway,
    NotConfiguredPaymentGateway,
    configure_payment_gateway,
)
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

logger = logging.getLogger(__name__)


def setup_payment_gateway() -> None:
    """Konfigurasi payment gateway semasa."""

    if PAYMENT_PROVIDER == "DEVELOPMENT":
        configure_payment_gateway(
            DevelopmentPaymentGateway()
        )

        logger.warning(
            "Development Payment Gateway aktif."
        )
        return

    if PAYMENT_PROVIDER == "BAYARCASH":
        configure_payment_gateway(
            NotConfiguredPaymentGateway()
        )

        logger.warning(
            "BayarCash aktif untuk Payment Intent. "
            "Pengaktifan subscription melalui "
            "webhook belum dipasang."
        )
        return

    configure_payment_gateway(
        NotConfiguredPaymentGateway()
    )

    logger.warning(
        "Payment gateway belum dikonfigurasi. "
        "Provider semasa: %s",
        PAYMENT_PROVIDER,
    )


def build_billing_conversation() -> ConversationHandler:
    """Bina flow perbualan Billing Profile."""

    return ConversationHandler(
        entry_points=[
            CommandHandler(
                "billing",
                billing_command,
            )
        ],
        states={
            BILLING_PHONE: [
                MessageHandler(
                    filters.CONTACT,
                    receive_billing_contact,
                ),
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    receive_billing_contact,
                ),
            ],
            BILLING_EMAIL: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    receive_billing_email,
                )
            ],
            BILLING_CONFIRM: [
                CallbackQueryHandler(
                    handle_billing_confirmation,
                    pattern=r"^billing:",
                )
            ],
        },
        fallbacks=[
            CommandHandler(
                "cancel",
                cancel_billing_command,
            )
        ],
        allow_reentry=True,
    )


async def setup_bot_commands(
    application: Application,
) -> None:
    """Daftar command Telegram."""

    commands = [
        BotCommand(
            "start",
            "Mulakan ReceiptBot",
        ),
        BotCommand(
            "dashboard",
            "Lihat dashboard perbelanjaan",
        ),
        BotCommand(
            "receipts",
            "Lihat resit terkini",
        ),
        BotCommand(
            "search",
            "Cari rekod resit",
        ),
        BotCommand(
            "export_csv",
            "Eksport rekod ke CSV",
        ),
        BotCommand(
            "summary",
            "Lihat ringkasan bulan ini",
        ),
        BotCommand(
            "account",
            "Lihat maklumat akaun",
        ),
        BotCommand(
            "billing",
            "Urus maklumat pembayaran",
        ),
        BotCommand(
            "upgrade",
            "Naik taraf pelan Biscotto ReceiptBot",
        ),
        BotCommand(
            "help",
            "Panduan Biscotto ReceiptBot",
        ),
    ]

    await application.bot.set_my_commands(
        commands
    )


def main() -> None:
    """Jalankan ReceiptBot."""

    setup_payment_gateway()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(setup_bot_commands)
        .build()
    )

    application.add_handler(
        build_billing_conversation()
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
            handle_development_payment_action,
            pattern=(
                "^"
                f"{CALLBACK_DEVELOPMENT_PAYMENT_PREFIX}"
            ),
        )
    )

    if PAYMENT_PROVIDER == "BAYARCASH":
        application.add_handler(
            CallbackQueryHandler(
                handle_bayarcash_checkout_action,
                pattern=(
                    "^"
                    f"{CALLBACK_BAYARCASH_CONFIRM_PREFIX}"
                ),
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