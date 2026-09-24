import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import (
    CREDENTIALS_ERROR,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.config import (
    DISPLAY_NAME_MAX,
    DISPLAY_NAME_MIN,
    DISPLAY_NAME_PATTERN,
    DISPLAY_NAME_RESERVED,
    MAX_PASSWORD_BYTES,
    MIN_PASSWORD_LENGTH,
)
from app import cache
from app.db import get_session
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_BYTES)
    display_name: str | None = Field(
        default=None,
        min_length=DISPLAY_NAME_MIN,
        max_length=DISPLAY_NAME_MAX,
        pattern=DISPLAY_NAME_PATTERN,
    )


class LoginCredentials(BaseModel):
    # login must not leak the password rules, so no length constraints here
    email: EmailStr
    password: str


def _token_response(user: User) -> dict:
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "email": user.email,
        "display_name": user.display_name,
    }


def _name_owner(session: Session, display_name: str) -> User | None:
    """Whoever holds this name, case-insensitively, matching the unique index."""
    return session.scalar(
        select(User).where(func.lower(User.display_name) == display_name.lower())
    )


def _check_name(session: Session, display_name: str, owner: User | None = None) -> str:
    """Validate a chosen name for signup or rename. Returns it stripped.

    One function for both paths: the rules have to be the same in each, and a
    second copy is how they stop being.
    """
    chosen = display_name.strip()
    # trader-<id> is how omitted names are filled in, so nobody may claim one:
    # that keeps the generated name for a new id always free
    if re.match(DISPLAY_NAME_RESERVED, chosen):
        raise HTTPException(status_code=409, detail="display name is reserved")
    held_by = _name_owner(session, chosen)
    if held_by is not None and (owner is None or held_by.id != owner.id):
        raise HTTPException(status_code=409, detail="display name already taken")
    return chosen


def _find_user(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email.strip().lower()))


@router.post("/signup", status_code=201)
def signup(body: Credentials, session: Session = Depends(get_session)):
    email = body.email.strip().lower()
    if _find_user(session, email) is not None:
        raise HTTPException(status_code=409, detail="email already registered")

    chosen = _check_name(session, body.display_name) if body.display_name else None

    # The default name needs the id, which only exists once the row does, so
    # insert under a placeholder and rename before commit. The placeholder is
    # unique because the index is enforced on insert, not at commit -- a shared
    # constant would make two concurrent signups collide.
    user = User(
        email=email,
        display_name=chosen or f"tmp-{uuid.uuid4().hex[:12]}",
        password_hash=hash_password(body.password),
    )
    session.add(user)
    session.flush()
    if chosen is None:
        user.display_name = f"trader-{user.id}"
    session.commit()
    return _token_response(user)


@router.post("/login")
def login(body: LoginCredentials, session: Session = Depends(get_session)):
    user = _find_user(session, body.email)
    # same error whether the email is unknown or the password is wrong, so the
    # endpoint cannot be used to discover which addresses are registered
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail=CREDENTIALS_ERROR)
    return _token_response(user)


class DisplayNameUpdate(BaseModel):
    display_name: str = Field(
        min_length=DISPLAY_NAME_MIN,
        max_length=DISPLAY_NAME_MAX,
        pattern=DISPLAY_NAME_PATTERN,
    )


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "display_name": user.display_name}


@router.patch("/me")
def rename(
    body: DisplayNameUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # owner=user, so re-submitting your own name is a no-op rather than a 409
    user.display_name = _check_name(session, body.display_name, owner=user)
    session.commit()
    # the ranking carries the old name until its TTL; a rename is the one
    # change a caller expects to see at once
    cache.clear_leaderboard()
    return {"id": user.id, "email": user.email, "display_name": user.display_name}
