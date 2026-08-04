import os
from functools import lru_cache

from supabase import Client, create_client


@lru_cache
def get_supabase_client() -> Client:
    supabase_url = os.getenv("SUPABASE_URL")

    supabase_key = (
        os.getenv("SUPABASE_SECRET_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )

    if not supabase_url:
        raise RuntimeError(
            "SUPABASE_URL não configurada no arquivo .env."
        )

    if not supabase_key:
        raise RuntimeError(
            "Configure SUPABASE_SECRET_KEY ou "
            "SUPABASE_SERVICE_ROLE_KEY no arquivo .env."
        )

    return create_client(
        supabase_url,
        supabase_key,
    )


def check_database_connection() -> dict[str, str]:
    client = get_supabase_client()

    client.table("startups").select("id").limit(1).execute()

    return {
        "status": "connected",
        "database": "Supabase",
        "table": "startups",
    }