from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import create_pool
from app.routers import auth, me


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = create_pool(get_settings().database_url)
    await pool.open()
    app.state.pool = pool
    yield
    await pool.close()


app = FastAPI(title="Gift lottery API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

api = APIRouter(prefix="/api")


@api.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


api.include_router(auth.router)
api.include_router(me.router)
app.include_router(api)
