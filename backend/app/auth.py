from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from psycopg import AsyncConnection

from app.config import get_settings
from app.db import get_conn
from app.schemas import Me

bearer = HTTPBearer(auto_error=False)


@lru_cache
def _jwks_client() -> PyJWKClient:
    return PyJWKClient(f"{get_settings().supabase_url}/auth/v1/.well-known/jwks.json")


def _unauthorized() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "unauthorized")


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> UUID:
    # Sync dependency: FastAPI runs it in a threadpool (PyJWKClient does blocking I/O).
    if credentials is None:
        raise _unauthorized()
    try:
        key = _jwks_client().get_signing_key_from_jwt(credentials.credentials)
        claims = jwt.decode(
            credentials.credentials,
            key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
        return UUID(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _unauthorized() from None


async def get_current_profile(
    user_id: UUID = Depends(get_current_user_id),
    conn: AsyncConnection = Depends(get_conn),
) -> Me:
    cur = await conn.execute(
        "select id, username, email, is_master from profiles where id = %s", (user_id,)
    )
    row = await cur.fetchone()
    if row is None:
        raise _unauthorized()
    return Me(**row)


async def require_master(profile: Me = Depends(get_current_profile)) -> Me:
    if not profile.is_master:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_master")
    return profile
