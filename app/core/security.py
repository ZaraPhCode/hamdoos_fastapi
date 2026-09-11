"""JWT token creation/verification and password hashing.

Mirrors the .NET Identity password hashing + custom JWT approach.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config.settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True iff the plain password matches the stored bcrypt hash.

    Passwords migrated from the legacy .NET Identity store are NOT bcrypt
    hashes — passlib raises (``hash could not be identified``) for those.
    A non-matching/legacy hash must be a plain ``False`` (wrong password),
    never an unhandled 500. Those users can sign in via OTP or reset their
    password, which re-hashes with bcrypt going forward.
    """
    try:
        if not plain_password or not hashed_password:
            return False
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=7)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None