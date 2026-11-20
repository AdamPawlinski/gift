from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from psycopg import AsyncConnection, errors
from psycopg.types.json import Jsonb
from supabase_auth.errors import AuthApiError

from app.db import get_conn
from app.schemas import RegisterRequest, RegisterResponse
from app.supabase_admin import get_admin_client

router = APIRouter(prefix="/auth", tags=["auth"])

CONSTRAINT_TO_DETAIL = {
    "profiles_username_ci": "username_taken",
}


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, conn: AsyncConnection = Depends(get_conn)):
    cur = await conn.execute(
        "select exists(select 1 from profiles where lower(username) = lower(%s)) as e",
        (body.username,),
    )
    if (await cur.fetchone())["e"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "username_taken")

    admin = get_admin_client()
    try:
        created = await run_in_threadpool(
            admin.auth.admin.create_user,
            {
                "email": body.email,
                "password": body.password,
                "email_confirm": True,
                "user_metadata": {"username": body.username},
            },
        )
    except AuthApiError as e:
        if e.code in ("email_exists", "user_already_exists"):
            raise HTTPException(status.HTTP_409_CONFLICT, "email_taken") from None
        if e.code == "weak_password":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "weak_password") from None
        raise
    user = created.user

    try:
        async with conn.transaction():
            await conn.execute(
                "insert into profiles (id, username, email) values (%s, %s, %s)",
                (user.id, body.username, user.email),
            )
            await conn.execute(
                "insert into lottery_logs (actor_id, action, details)"
                " values (%s, 'user_registered', %s)",
                (user.id, Jsonb({})),
            )
    except errors.UniqueViolation as e:
        # Lost a race against another registration: roll back the auth user.
        await run_in_threadpool(admin.auth.admin.delete_user, user.id)
        detail = CONSTRAINT_TO_DETAIL.get(e.diag.constraint_name, "conflict")
        raise HTTPException(status.HTTP_409_CONFLICT, detail) from None
    except Exception:
        await run_in_threadpool(admin.auth.admin.delete_user, user.id)
        raise

    return RegisterResponse(id=user.id)
