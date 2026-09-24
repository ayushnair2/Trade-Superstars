from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_session
from app.lessons.concepts import GLOBAL_CONCEPTS, Concept
from app.lessons.provider import LessonProviderError
from app.lessons.service import lesson_for_concept, lesson_for_trade
from app.models import Trade, User

router = APIRouter(prefix="/lessons", tags=["lessons"])


class ForTradeRequest(BaseModel):
    trade_id: int


class ForConceptRequest(BaseModel):
    concept: str


@router.post("/for-trade")
def for_trade(
    body: ForTradeRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    trade = session.get(Trade, body.trade_id)
    # someone else's trade is reported as missing rather than forbidden, so the
    # endpoint cannot be used to probe which trade ids exist
    if trade is None or trade.user_id != user.id:
        raise HTTPException(status_code=404, detail="trade not found")
    try:
        return lesson_for_trade(session, trade)
    except LessonProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/for-concept")
def for_concept(
    body: ForConceptRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """A lesson for something that is not a trade -- buying a bond, say.

    Global concepts only. Those are cached under one key and served to every
    user, so there is nothing here that could be specific to the caller; a
    player-specific concept would have no athlete to attach to anyway.
    """
    try:
        concept = Concept(body.concept)
    except ValueError:
        raise HTTPException(status_code=404, detail="unknown concept") from None
    if concept not in GLOBAL_CONCEPTS:
        raise HTTPException(status_code=400, detail="concept is not global")
    try:
        return lesson_for_concept(session, concept)
    except LessonProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
