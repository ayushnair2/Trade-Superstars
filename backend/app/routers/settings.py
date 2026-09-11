from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_session
from app.models import User
from app.ticker import get_settings

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    day_length_minutes: int = Field(ge=1, le=120)
    ticks_per_day: int = Field(ge=1, le=200)
    randomness: str = "fully_random"


def _as_dict(settings) -> dict:
    return {
        "day_length_minutes": settings.day_length_minutes,
        "ticks_per_day": settings.ticks_per_day,
        "randomness": settings.randomness,
        "updated_at": settings.updated_at.isoformat(),
    }


@router.get("")
def read_settings(session: Session = Depends(get_session)):
    settings = get_settings(session)
    session.commit()
    return _as_dict(settings)


@router.put("")
def update_settings(
    body: SettingsUpdate,
    session: Session = Depends(get_session),
    # These settings drive the SHARED market clock, so a change affects every
    # player. Requiring any logged-in user is the interim rule; if this ever
    # needs to be an admin-only control, tighten it here.
    user: User = Depends(get_current_user),
):
    settings = get_settings(session)
    settings.day_length_minutes = body.day_length_minutes
    settings.ticks_per_day = body.ticks_per_day
    settings.randomness = body.randomness
    session.commit()
    return _as_dict(settings)
