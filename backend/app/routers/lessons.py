from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session
from app.lessons.provider import LessonProviderError
from app.lessons.service import lesson_for_trade
from app.models import Trade

router = APIRouter(prefix="/lessons", tags=["lessons"])


class ForTradeRequest(BaseModel):
    trade_id: int


@router.post("/for-trade")
def for_trade(body: ForTradeRequest, session: Session = Depends(get_session)):
    trade = session.get(Trade, body.trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="trade not found")
    try:
        return lesson_for_trade(session, trade)
    except LessonProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
