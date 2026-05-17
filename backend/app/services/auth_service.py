from dataclasses import dataclass

from fastapi import HTTPException, status
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.security import (
    access_token_key,
    create_access_token,
    create_refresh_token,
    decode_token,
    refresh_token_key,
)
from ..models.user import User
from ..schemas.auth import AuthSessionResponse, UserResponse
from .wechat_service import exchange_code_for_session


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    access_expires_in_seconds: int
    refresh_expires_in_seconds: int
    user: User


def token_response(tokens: IssuedTokens) -> AuthSessionResponse:
    return AuthSessionResponse(
        message="Authenticated",
        expires_in_seconds=tokens.access_expires_in_seconds,
        refresh_expires_in_seconds=tokens.refresh_expires_in_seconds,
        user=UserResponse.model_validate(tokens.user),
    )


def _issue_and_store_tokens(redis: Redis, user: User) -> IssuedTokens:
    access_token, access_jti = create_access_token(str(user.id))
    refresh_token, refresh_jti = create_refresh_token(str(user.id))
    access_expires = settings.access_token_expire_minutes * 60
    refresh_expires = settings.refresh_token_expire_minutes * 60
    redis.set(
        access_token_key(user.id, access_jti),
        access_token,
        ex=access_expires,
    )
    redis.set(
        refresh_token_key(user.id, refresh_jti),
        refresh_token,
        ex=refresh_expires,
    )
    return IssuedTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_in_seconds=access_expires,
        refresh_expires_in_seconds=refresh_expires,
        user=user,
    )


def _revoke_token(redis: Redis, token: str, expected_type: str) -> None:
    try:
        payload = decode_token(token, expected_type=expected_type)
    except Exception:
        return
    user_id = payload["sub"]
    jti = payload["jti"]
    key = (
        access_token_key(user_id, jti)
        if expected_type == "access"
        else refresh_token_key(user_id, jti)
    )
    redis.delete(key)


def login_with_wechat_code(
    db: Session,
    redis: Redis,
    code: str,
    nickname: str | None = None,
) -> IssuedTokens:
    session = exchange_code_for_session(code)
    openid = session["openid"]

    user = db.scalar(select(User).where(User.openid == openid))
    if user is None:
        user = User(
            email=None,
            username=f"wx_{openid}",
            openid=openid,
            nickname=nickname,
        )
        db.add(user)
    elif nickname and not user.nickname:
        user.nickname = nickname

    db.commit()
    db.refresh(user)
    return _issue_and_store_tokens(redis, user)


def refresh_user_tokens(
    db: Session,
    redis: Redis,
    refresh_token: str | None,
) -> IssuedTokens:
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
    )
    if not refresh_token:
        raise auth_error
    try:
        token_payload = decode_token(refresh_token, expected_type="refresh")
    except Exception as exc:
        raise auth_error from exc

    user_id = int(token_payload["sub"])
    refresh_jti = str(token_payload["jti"])
    stored_token = redis.get(refresh_token_key(user_id, refresh_jti))
    if stored_token != refresh_token:
        raise auth_error

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise auth_error

    redis.delete(refresh_token_key(user_id, refresh_jti))
    return _issue_and_store_tokens(redis, user)


def logout_user(
    redis: Redis,
    access_token: str | None = None,
    refresh_token: str | None = None,
) -> None:
    if access_token:
        _revoke_token(redis, access_token, expected_type="access")
    if refresh_token:
        _revoke_token(redis, refresh_token, expected_type="refresh")
