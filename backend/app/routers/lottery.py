from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from psycopg import AsyncConnection, errors
from psycopg.types.json import Jsonb

from app import email
from app.auth import get_current_profile, require_master
from app.config import Settings, get_settings
from app.db import get_conn
from app.draw import draw
from app.schemas import LotteryCreated, LotteryCurrent, Me, Participant

router = APIRouter(tags=["lottery"])


async def _active_lottery_id(conn: AsyncConnection) -> UUID | None:
    cur = await conn.execute("select id from lotteries where status = 'finished'")
    row = await cur.fetchone()
    return row["id"] if row else None


async def _receiver_username(conn: AsyncConnection, lottery_id: UUID, giver_id: UUID) -> str | None:
    cur = await conn.execute(
        "select p.username from lottery_results r"
        " join profiles p on p.id = r.receiver_id"
        " where r.lottery_id = %s and r.giver_id = %s",
        (lottery_id, giver_id),
    )
    row = await cur.fetchone()
    return row["username"] if row else None


@router.get("/lottery/current", response_model=LotteryCurrent)
async def current_lottery(
    profile: Me = Depends(get_current_profile), conn: AsyncConnection = Depends(get_conn)
):
    lottery_id = await _active_lottery_id(conn)
    if lottery_id is None:
        return LotteryCurrent(status="not_started")
    receiver = await _receiver_username(conn, lottery_id, profile.id)
    return LotteryCurrent(
        status="finished",
        lottery_id=lottery_id,
        participated=receiver is not None,
        receiver_username=receiver,
    )


@router.get("/participants", response_model=list[Participant])
async def participants(_: Me = Depends(require_master), conn: AsyncConnection = Depends(get_conn)):
    cur = await conn.execute("select username from profiles order by created_at")
    return await cur.fetchall()


@router.post("/lottery", response_model=LotteryCreated, status_code=status.HTTP_201_CREATED)
async def start_lottery(
    master: Me = Depends(require_master),
    conn: AsyncConnection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
):
    # Lock the profiles so nobody registers between reading the list and drawing.
    cur = await conn.execute("select id from profiles order by created_at for update")
    ids = [row["id"] for row in await cur.fetchall()]
    if len(ids) < max(settings.min_participants, 2):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "not_enough_participants")

    pairs = draw(ids)
    try:
        async with conn.transaction():
            cur = await conn.execute(
                "insert into lotteries (status, started_by) values ('finished', %s) returning id",
                (master.id,),
            )
            lottery_id = (await cur.fetchone())["id"]
            async with conn.cursor() as c:
                await c.executemany(
                    "insert into lottery_results (lottery_id, giver_id, receiver_id)"
                    " values (%s, %s, %s)",
                    [(lottery_id, giver, receiver) for giver, receiver in pairs.items()],
                )
            await conn.execute(
                "insert into lottery_logs (lottery_id, actor_id, action, details)"
                " values (%s, %s, 'lottery_started', %s)",
                (lottery_id, master.id, Jsonb({"participants": len(ids)})),
            )
    except errors.UniqueViolation:
        raise HTTPException(status.HTTP_409_CONFLICT, "lottery_active") from None
    return LotteryCreated(lottery_id=lottery_id)


@router.delete("/lottery/current", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_lottery(
    master: Me = Depends(require_master), conn: AsyncConnection = Depends(get_conn)
):
    cur = await conn.execute(
        "update lotteries set status = 'cancelled', cancelled_by = %s, cancelled_at = now()"
        " where status = 'finished' returning id",
        (master.id,),
    )
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_active_lottery")
    await conn.execute(
        "insert into lottery_logs (lottery_id, actor_id, action) values (%s, %s, 'lottery_cancelled')",
        (row["id"], master.id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/lottery/current/email", status_code=status.HTTP_202_ACCEPTED)
async def email_result(
    profile: Me = Depends(get_current_profile),
    conn: AsyncConnection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
):
    lottery_id = await _active_lottery_id(conn)
    receiver = await _receiver_username(conn, lottery_id, profile.id) if lottery_id else None
    if receiver is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_result")

    cur = await conn.execute(
        "select exists(select 1 from lottery_logs where action = 'result_email_sent'"
        " and lottery_id = %s and actor_id = %s"
        " and created_at > now() - make_interval(mins => %s)) as e",
        (lottery_id, profile.id, settings.email_cooldown_minutes),
    )
    if (await cur.fetchone())["e"]:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")

    await email.send_result(profile.email, profile.username, receiver)
    await conn.execute(
        "insert into lottery_logs (lottery_id, actor_id, action) values (%s, %s, 'result_email_sent')",
        (lottery_id, profile.id),
    )
    return {"status": "sent"}
