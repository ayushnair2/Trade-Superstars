"""Password hashing, JWT issuing, and the current-user dependency."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ACCESS_TOKEN_DAYS, JWT_ALGORITHM, MAX_PASSWORD_BYTES
from app.db import get_session
from app.models import User

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

CREDENTIALS_ERROR = "invalid email or password"


def jwt_secret() -> str:
    """The signing secret. Missing it is a deployment error, not a runtime one."""
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET is not set -- auth cannot run without it (see docs/deploy.md)"
        )
    return secret


def hash_password(password: str) -> str:
    # guarded by the signup schema too, but never let bcrypt's 72-byte limit
    # surface as a 500
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        raise ValueError("password too long")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        # an over-long or malformed candidate simply does not match
        return False


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "iat": now,
        "exp": now + timedelta(days=ACCESS_TOKEN_DAYS),
    }
    return jwt.encode(payload, jwt_secret(), algorithm=JWT_ALGORITHM)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized()
    return token.strip()


def get_current_user(
    request: Request, session: Session = Depends(get_session)
) -> User:
    """Resolve the Bearer token to a user, or 401. Used to protect endpoints."""
    token = _bearer_token(request)
    try:
        payload = jwt.decode(token, jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        # expired, wrong signature, malformed -- all the same to the caller
        raise _unauthorized() from None

    # a missing or non-numeric subject is a token we did not issue -- 401, not
    # a 500 from int()
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise _unauthorized() from None

    user = session.scalar(select(User).where(User.id == user_id))
    if user is None:
        # token was valid but the account is gone
        raise _unauthorized()
    return user
