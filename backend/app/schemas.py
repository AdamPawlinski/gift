from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, StringConstraints

DrawName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Username = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=30)]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=6, max_length=72)]
    username: Username


class RegisterResponse(BaseModel):
    id: UUID


class DeleteAccountRequest(BaseModel):
    password: Annotated[str, StringConstraints(min_length=1, max_length=72)]


class Me(BaseModel):
    id: UUID
    username: str
    email: str
    draw_id: UUID | None = None
    draw_name: str | None = None
    is_master: bool = False


class LotteryCurrent(BaseModel):
    status: Literal["no_draw", "not_started", "finished"]
    lottery_id: UUID | None = None
    participated: bool = False
    receiver_username: str | None = None


class LotteryCreated(BaseModel):
    lottery_id: UUID


class Participant(BaseModel):
    username: str


class CreateDrawRequest(BaseModel):
    name: DrawName


class DrawSummary(BaseModel):
    id: UUID
    name: str
    members: int
