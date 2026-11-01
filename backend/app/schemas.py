from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, EmailStr, StringConstraints

Username = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=30)]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=6, max_length=72)]
    username: Username
    is_master: bool = False


class RegisterResponse(BaseModel):
    id: UUID


class MasterAvailability(BaseModel):
    available: bool


class Me(BaseModel):
    id: UUID
    username: str
    email: str
    is_master: bool
