from functools import lru_cache

import httpx
from fastapi import HTTPException, status
from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_admin_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


async def verify_password(email: str, password: str) -> bool:
    """Check the credentials with a password grant, without touching the shared admin client."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{settings.supabase_url}/auth/v1/token",
                params={"grant_type": "password"},
                json={"email": email, "password": password},
                headers={"apikey": settings.supabase_service_role_key},
            )
    except httpx.HTTPError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "auth_failed") from None
    if response.status_code == 200:
        return True
    if response.status_code == 400:
        return False
    raise HTTPException(status.HTTP_502_BAD_GATEWAY, "auth_failed")
