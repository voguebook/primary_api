from supabase import create_client, Client
from typing import Optional


def supabaseClient(url: str, key: str, schema: Optional[str] = "tb2"):
    client = create_client(url, key).schema(schema)
    return client
