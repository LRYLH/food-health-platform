from dataclasses import dataclass

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.security import (
    access_token_key,
    create_access_token,
)
from ..models.user import User
from .wechat_service import exchange_code_for_session


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    access_expires_in_seconds: int
    user: User
    is_new_user: bool = False


def _issue_and_store_tokens(redis: Redis, user: User, *, is_new_user: bool = False) -> IssuedTokens:
    access_token, access_jti = create_access_token(str(user.id))
    access_expires = settings.access_token_expire_minutes * 60
    redis.set(
        access_token_key(user.id, access_jti),
        access_token,
        ex=access_expires,
    )
    return IssuedTokens(
        access_token=access_token,
        access_expires_in_seconds=access_expires,
        user=user,
        is_new_user=is_new_user,
    )


def login_with_wechat_code(
    db: Session,
    redis: Redis,
    code: str,
    nickname: str | None = None,
) -> IssuedTokens:
    session = exchange_code_for_session(code)
    openid = session["openid"]

    user = db.scalar(select(User).where(User.openid == openid))
    is_new_user = user is None
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
    return _issue_and_store_tokens(redis, user, is_new_user=is_new_user)


def login_with_mock_user(
    db: Session,
    redis: Redis,
    username: str = "dev_user",
    nickname: str | None = "Mock User",
) -> IssuedTokens:
    safe_username = "".join(
        char if char.isalnum() or char in ("_", "-") else "_"
        for char in username.strip()
    )[:64] or "dev_user"
    mock_openid = f"mock_{safe_username}"
    user = db.scalar(select(User).where(User.openid == mock_openid))
    is_new_user = user is None
    if user is None:
        user = User(
            email=None,
            username=mock_openid,
            openid=mock_openid,
            nickname=nickname,
        )
        db.add(user)
    elif nickname and not user.nickname:
        user.nickname = nickname

    db.commit()
    db.refresh(user)
    return _issue_and_store_tokens(redis, user, is_new_user=is_new_user)
