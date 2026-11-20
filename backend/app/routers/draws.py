from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from psycopg import AsyncConnection, errors
from psycopg.types.json import Jsonb

from app.auth import get_current_profile
from app.db import get_conn
from app.routers.lottery import active_lottery_id, cancel_active_lottery
from app.schemas import CreateDrawRequest, DrawSummary, Me

router = APIRouter(tags=["draws"])


async def _log(conn: AsyncConnection, draw_id: UUID, actor_id: UUID, action: str, details=None):
    await conn.execute(
        "insert into lottery_logs (draw_id, actor_id, action, details) values (%s, %s, %s, %s)",
        (draw_id, actor_id, action, Jsonb(details or {})),
    )


async def leave_draw(conn: AsyncConnection, profile: Me, reason: str) -> None:
    """Remove the user from the draw. The master closes the draw for all members."""
    draw_id = profile.draw_id
    if profile.is_master:
        await cancel_active_lottery(conn, draw_id, profile.id, {"reason": "draw_closed"})
        await conn.execute(
            "update draws set closed_at = now(), closed_by = %s where id = %s",
            (profile.id, draw_id),
        )
        await conn.execute(
            "update profiles set draw_id = null, joined_at = null where draw_id = %s", (draw_id,)
        )
        await _log(conn, draw_id, profile.id, "draw_closed", {"reason": reason})
    else:
        await cancel_active_lottery(conn, draw_id, profile.id, {"reason": "member_left"})
        await conn.execute(
            "update profiles set draw_id = null, joined_at = null where id = %s", (profile.id,)
        )
        await _log(conn, draw_id, profile.id, "draw_left", {"reason": reason})


@router.get("/draws", response_model=list[DrawSummary])
async def list_draws(_: Me = Depends(get_current_profile), conn: AsyncConnection = Depends(get_conn)):
    cur = await conn.execute(
        "select d.id, d.name, count(p.id)::int as members"
        " from draws d left join profiles p on p.draw_id = d.id and p.deleted_at is null"
        " where d.closed_at is null"
        " and not exists (select 1 from lotteries l where l.draw_id = d.id and l.status = 'finished')"
        " group by d.id order by lower(d.name)"
    )
    return await cur.fetchall()


@router.post("/draws", response_model=DrawSummary, status_code=status.HTTP_201_CREATED)
async def create_draw(
    body: CreateDrawRequest,
    profile: Me = Depends(get_current_profile),
    conn: AsyncConnection = Depends(get_conn),
):
    if profile.draw_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_in_draw")
    try:
        async with conn.transaction():
            cur = await conn.execute(
                "insert into draws (name, master_id) values (%s, %s) returning id, name",
                (body.name, profile.id),
            )
            draw = await cur.fetchone()
            cur = await conn.execute(
                "update profiles set draw_id = %s, joined_at = now()"
                " where id = %s and draw_id is null returning id",
                (draw["id"], profile.id),
            )
            if await cur.fetchone() is None:
                raise HTTPException(status.HTTP_409_CONFLICT, "already_in_draw")
            await _log(conn, draw["id"], profile.id, "draw_created", {"name": draw["name"]})
    except errors.UniqueViolation:
        raise HTTPException(status.HTTP_409_CONFLICT, "draw_name_taken") from None
    return DrawSummary(id=draw["id"], name=draw["name"], members=1)


@router.post("/draws/{draw_id}/join", status_code=status.HTTP_204_NO_CONTENT)
async def join_draw(
    draw_id: UUID,
    profile: Me = Depends(get_current_profile),
    conn: AsyncConnection = Depends(get_conn),
):
    if profile.draw_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_in_draw")
    async with conn.transaction():
        # The lock stops the master from starting the lottery while the user joins.
        cur = await conn.execute(
            "select id from draws where id = %s and closed_at is null for update", (draw_id,)
        )
        if await cur.fetchone() is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "draw_not_found")
        if await active_lottery_id(conn, draw_id) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "lottery_active")
        cur = await conn.execute(
            "update profiles set draw_id = %s, joined_at = now()"
            " where id = %s and draw_id is null returning id",
            (draw_id, profile.id),
        )
        if await cur.fetchone() is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "already_in_draw")
        await _log(conn, draw_id, profile.id, "draw_joined")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/draw/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave(profile: Me = Depends(get_current_profile), conn: AsyncConnection = Depends(get_conn)):
    if profile.draw_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_in_draw")
    async with conn.transaction():
        await leave_draw(conn, profile, "left")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
