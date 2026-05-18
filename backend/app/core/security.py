from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from redis import Redis
from sqlalchemy.orm import Session

from ..models.user import User
from .config import settings
from .database import get_db
from .redis_client import get_redis


def create_token(
    *,
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    jti: str | None = None,
) -> tuple[str, str]:
    if not settings.secret_key:
        raise RuntimeError("SECRET_KEY must be configured")
    token_jti = jti or uuid4().hex
    expires_at = datetime.now(UTC) + expires_delta
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expires_at,
        "type": token_type,
        "jti": token_jti,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, token_jti


def create_access_token(subject: str) -> tuple[str, str]:
    return create_token(
        subject=subject,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(subject: str) -> tuple[str, str]:
    return create_token(
        subject=subject,
        token_type="refresh",
        expires_delta=timedelta(minutes=settings.refresh_token_expire_minutes),
    )


def access_token_key(user_id: int | str, jti: str) -> str:
    return f"auth:access:{user_id}:{jti}"


def refresh_token_key(user_id: int | str, jti: str) -> str:
    return f"auth:refresh:{user_id}:{jti}"


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    if not settings.secret_key:
        raise JWTError("SECRET_KEY must be configured")
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != expected_type:
        raise JWTError("Invalid token type")
    if not payload.get("sub") or not payload.get("jti"):
        raise JWTError("Missing token claims")
    return payload


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    authorization = request.headers.get("Authorization", "")
    scheme, _, bearer_token = authorization.partition(" ")
    access_token = (
        bearer_token.strip()
        if scheme.lower() == "bearer" and bearer_token.strip()
        else request.cookies.get(settings.access_token_cookie_name)
    )
    if not access_token:
        raise auth_error

    try:
        payload = decode_token(access_token, expected_type="access")
        user_id = payload.get("sub")
        jti = payload.get("jti")
    except JWTError as exc:
        raise auth_error from exc

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise auth_error

    stored_token = redis.get(access_token_key(user.id, str(jti)))
    if stored_token != access_token:
        raise auth_error
    return user
