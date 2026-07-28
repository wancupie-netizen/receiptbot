import os

from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.getenv(
    "BOT_TOKEN"
)

SUPABASE_URL = os.getenv(
    "SUPABASE_URL"
)

SUPABASE_SECRET_KEY = os.getenv(
    "SUPABASE_SECRET_KEY"
)

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY"
)

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4.1-mini",
)

PAYMENT_PROVIDER = os.getenv(
    "PAYMENT_PROVIDER",
    "DEVELOPMENT",
).strip().upper()


if not BOT_TOKEN:
    raise ValueError(
        "BOT_TOKEN tidak dijumpai dalam fail .env"
    )

if not SUPABASE_URL:
    raise ValueError(
        "SUPABASE_URL tidak dijumpai dalam fail .env"
    )

if not SUPABASE_SECRET_KEY:
    raise ValueError(
        "SUPABASE_SECRET_KEY tidak dijumpai "
        "dalam fail .env"
    )

if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY tidak dijumpai "
        "dalam fail .env"
    )

if PAYMENT_PROVIDER not in {
    "DEVELOPMENT",
    "NOT_CONFIGURED",
    "BILLPLZ",
    "BAYARCASH",
}:
    raise ValueError(
        "PAYMENT_PROVIDER tidak sah. "
        "Gunakan DEVELOPMENT, NOT_CONFIGURED, "
        "BILLPLZ atau BAYARCASH."
    )