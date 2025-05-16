from typing import Optional
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from services.cloud import supabase  # Assuming this is your Supabase client
from supabase import Client, create_client
import os
from dotenv import load_dotenv
from cachetools import TTLCache

# Max 100 users, 5 min TTL
_user_meta_cache = TTLCache(maxsize=100, ttl=1)

load_dotenv()


security = HTTPBearer()

supabase: Client = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_KEY"),
)


class User(BaseModel):
    id: str
    country: Optional[str] = "DK"
    currency: Optional[str] = "DKK"
    gender: Optional[str] = None


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="No credentials provided")

    token = credentials.credentials

    # Try token cache

    try:
        user = supabase.auth.get_user(token)
        user_id = user.user.id if user and hasattr(user, "user") and user.user else None
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")

    except Exception as e:
        print(f"Token validation error: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Try metadata cache
    if user_id in _user_meta_cache:
        return _user_meta_cache[user_id]

    try:
        user_meta = (
            supabase.schema("tb2")
            .table("users")
            .select("country, currency")
            .eq("id", user_id)
            .execute()
        )
        user_data = user_meta.data[0] if user_meta.data else {}
        user_data["id"] = user_id
        user_model = User(**user_data)
        _user_meta_cache[user_id] = user_model  # Cache user profile
        return user_model
    except Exception as e:
        print(f"User metadata fetch error: {e}")
        return User(id=user_id)
