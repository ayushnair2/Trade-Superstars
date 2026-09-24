"""Public leaderboard. Optional auth: signing in only adds your own row."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app import cache
from app.auth import get_current_user
from app.config import LEADERBOARD_TOP_N
from app.db import get_session
from app.leaderboard import public_entry, ranked_rows
from app.models import User

router = APIRouter(tags=["leaderboard"])


def optional_user(
    request: Request, session: Session = Depends(get_session)
) -> User | None:
    """The caller if they are signed in, otherwise None. The board is public,
    so a missing or bad token is not an error here."""
    try:
        return get_current_user(request, session)
    except Exception:
        return None


@router.get("/leaderboard")
def leaderboard(
    top: int = Query(default=LEADERBOARD_TOP_N, ge=1, le=LEADERBOARD_TOP_N),
    session: Session = Depends(get_session),
    user: User | None = Depends(optional_user),
):
    # cache-aside: a hit serves the stored ranking, a miss computes and stores
    rows = cache.read_leaderboard()
    if rows is None:
        rows = ranked_rows(session)
        cache.write_leaderboard(rows)

    body = {
        "top": [public_entry(row) for row in rows[:top]],
        "total_players": len(rows),
    }

    if user is not None:
        mine = next((row for row in rows if row["user_id"] == user.id), None)
        # only when they fell outside the slice, so the caller never sees
        # themselves twice
        if mine is not None and mine["rank"] > top:
            body["me"] = public_entry(mine)
    return body
