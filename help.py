import logging

from telegram import Update
from telegram.ext import ContextTypes


logger = logging.getLogger(__name__)


HELP_MESSAGE = """
🤖 ReceiptBot

Selamat datang ke ReceiptBot.

ReceiptBot membantu anda menyimpan
resit dan merekod perbelanjaan
terus daripada Telegram.

━━━━━━━━━━━━━━

📸 Cara Guna

1️⃣ Hantar gambar resit.

2️⃣ AI ReceiptBot akan membaca maklumat pada resit.

3️⃣ Semak dan betulkan jika perlu.

4️⃣ Tekan ✅ Sahkan untuk menyimpan.

━━━━━━━━━━━━━━

📋 Command

/start
Mulakan ReceiptBot

/dashboard
Dashboard perbelanjaan

/receipts
10 resit terkini

/search
Cari rekod resit

/summary
Ringkasan bulan ini

/account
Maklumat akaun

/help
Paparan bantuan

━━━━━━━━━━━━━━

🔎 Cara Carian

Gunakan:
/search kata_kunci

Contoh:
/search 99 Speed Mart
/search Bahan Mentah
/search 2026-07-27
/search 14.00

Carian resit tersedia untuk
pelan Starter dan Business.

━━━━━━━━━━━━━━

💡 Tip

• Ambil gambar yang jelas.

• Pastikan keseluruhan resit kelihatan.

• Elakkan gambar kabur.

━━━━━━━━━━━━━━

Terima kasih menggunakan
ReceiptBot ❤️
""".strip()


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Paparkan bantuan pengguna."""

    if update.message is None:
        return

    await update.message.reply_text(
        HELP_MESSAGE
    )