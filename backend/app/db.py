from collections.abc import AsyncIterator

from fastapi import Request
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


def create_pool(database_url: str) -> AsyncConnectionPool:
    return AsyncConnectionPool(
        database_url,
        min_size=0,
        max_size=3,
        open=False,
        kwargs={"row_factory": dict_row, "prepare_threshold": None},
    )


async def get_conn(request: Request) -> AsyncIterator[AsyncConnection]:
    async with request.app.state.pool.connection() as conn:
        yield conn
