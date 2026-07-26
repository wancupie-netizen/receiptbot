import os

from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv(
    "SUPABASE_SECRET_KEY"
)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash",
)


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

if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY tidak dijumpai dalam fail .env"
    )