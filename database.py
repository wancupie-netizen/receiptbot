from typing import Any

from supabase import Client, create_client

from config import SUPABASE_SECRET_KEY, SUPABASE_URL


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
)


def get_or_create_user(
    telegram_id: int,
    name: str,
) -> tuple[dict[str, Any], bool]:
    """
    Cari pengguna berdasarkan Telegram ID.

    Returns:
        tuple[user_data, is_new_user]
    """

    existing_user = (
        supabase.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .limit(1)
        .execute()
    )

    if existing_user.data:
        return existing_user.data[0], False

    new_user = (
        supabase.table("users")
        .insert(
            {
                "telegram_id": telegram_id,
                "name": name,
            }
        )
        .execute()
    )

    if not new_user.data:
        raise RuntimeError(
            "Supabase tidak memulangkan data pengguna baharu."
        )

    return new_user.data[0], True