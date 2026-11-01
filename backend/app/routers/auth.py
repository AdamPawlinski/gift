from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from psycopg import AsyncConnection, errors
from psycopg.types.json import Jsonb
from supabase_auth.errors import AuthApiError

from app.db import get_conn
from app.schemas import MasterAvailability, RegisterRequest, RegisterResponse
from app.supabase_admin import get_admin_client

router = APIRouter(prefix="/auth", tags=["auth"])

CONSTRAINT_TO_DETAIL = {
    "profiles_username_ci": "username_taken",
    "profiles_single_master": "master_taken",
}


async def _master_exists(conn: AsyncConnection) -> bool:
    cur = await conn.execute("select exists(select 1 from profiles where is_master) as e")
    return (await cur.fetchone())["e"]


@router.get("/master-available", response_model=MasterAvailability)
async def master_available(conn: AsyncConnection = Depends(get_conn)):
    return MasterAvailability(available=not await _master_exists(conn))


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, conn: AsyncConnection = Depends(get_conn)):
    cur = await conn.execute(
        "select exists(select 1 from profiles where lower(username) = lower(%s)) as e",
        (body.username,),
    )
    if (await cur.fetchone())["e"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "username_taken")
    if body.is_master and await _master_exists(conn):
        raise HTTPException(status.HTTP_409_CONFLICT, "master_taken")

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
                "insert into profiles (id, username, email, is_master) values (%s, %s, %s, %s)",
                (user.id, body.username, user.email, body.is_master),
            )
            await conn.execute(
                "insert into lottery_logs (actor_id, action, details)"
                " values (%s, 'user_registered', %s)",
                (user.id, Jsonb({"is_master": body.is_master})),
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
