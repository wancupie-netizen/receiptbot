from database import supabase


def main() -> None:
    try:
        response = (
            supabase.table("users")
            .select("*")
            .limit(1)
            .execute()
        )

        print("Sambungan Supabase berjaya ✅")
        print("Data:", response.data)

    except Exception as error:
        print("Sambungan Supabase gagal ❌")
        print("Jenis error:", type(error).__name__)
        print("Butiran error:", error)


if __name__ == "__main__":
    main()