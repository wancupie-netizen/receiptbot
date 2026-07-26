import logging

from telegram.ext import Application, CommandHandler

from bot import start
from config import BOT_TOKEN


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)


def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(
        CommandHandler("start", start)
    )

    print("ReceiptBot sedang berjalan...")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()