from fastapi import APIRouter, Depends

from app.auth import get_current_profile
from app.schemas import Me

router = APIRouter(tags=["me"])


@router.get("/me", response_model=Me)
async def me(profile: Me = Depends(get_current_profile)):
    return profile
