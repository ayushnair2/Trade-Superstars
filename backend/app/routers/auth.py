from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    CREDENTIALS_ERROR,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.config import MAX_PASSWORD_BYTES, MIN_PASSWORD_LENGTH
from app.db import get_session
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_BYTES)


class LoginCredentials(BaseModel):
    # login must not leak the password rules, so no length constraints here
    email: EmailStr
    password: str


def _token_response(user: User) -> dict:
    return {"access_token": create_access_token(user), "token_type": "bearer", "email": user.email}


def _find_user(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email.strip().lower()))


@router.post("/signup", status_code=201)
def signup(body: Credentials, session: Session = Depends(get_session)):
    email = body.email.strip().lower()
    if _find_user(session, email) is not None:
        raise HTTPException(status_code=409, detail="email already registered")

    user = User(email=email, password_hash=hash_password(body.password))
    session.add(user)
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


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email}
