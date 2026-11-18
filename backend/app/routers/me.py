from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.concurrency import run_in_threadpool
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb
from supabase_auth.errors import AuthApiError

from app.auth import get_current_profile
from app.db import get_conn
from app.routers.lottery import cancel_active_lottery
from app.schemas import DeleteAccountRequest, Me
from app.supabase_admin import get_admin_client, verify_password

router = APIRouter(tags=["me"])


@router.get("/me", response_model=Me)
async def me(profile: Me = Depends(get_current_profile)):
    return profile


@router.post("/me/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    body: DeleteAccountRequest,
    profile: Me = Depends(get_current_profile),
    conn: AsyncConnection = Depends(get_conn),
):
    if not await verify_password(profile.email, body.password):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "wrong_password")

    admin = get_admin_client()
    async with conn.transaction():
        cur = await conn.execute(
            "select exists(select 1 from lottery_results r join lotteries l on l.id = r.lottery_id"
            " where l.status = 'finished' and r.giver_id = %s) as e",
            (profile.id,),
        )
        if (await cur.fetchone())["e"]:
            await cancel_active_lottery(conn, profile.id, {"reason": "account_deleted"})
        await conn.execute(
            "update profiles set username = null, email = null, is_master = false,"
            " deleted_at = now() where id = %s",
            (profile.id,),
        )
        await conn.execute(
            "insert into lottery_logs (actor_id, action, details)"
            " values (%s, 'account_deleted', %s)",
            (profile.id, Jsonb({"was_master": profile.is_master})),
        )
        try:
            await run_in_threadpool(admin.auth.admin.delete_user, str(profile.id))
        except AuthApiError:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "delete_failed") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
