from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError as PyJWTInvalidTokenError
from passlib.context import CryptContext
from passlib.exc import UnknownHashError

from app.core.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class InvalidTokenError(Exception):
    """Raised when a JWT is invalid or expired."""


def normalize_email(email: str) -> str:
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise ValueError("Email must not be empty.")
    return normalized_email


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty.")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, UnknownHashError):
        return False


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        if not isinstance(payload, dict):
            raise InvalidTokenError("Invalid token payload.")
        return payload
    except ExpiredSignatureError as exc:
        raise InvalidTokenError("Token has expired.") from exc
    except PyJWTInvalidTokenError as exc:
        raise InvalidTokenError("Invalid token.") from exc