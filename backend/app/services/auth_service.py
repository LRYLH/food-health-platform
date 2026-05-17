from datetime import datetime, timedelta
import logging
import secrets

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
    hash_password,
    refresh_token_key,
    verify_password,
)
from ..models.email_verification import (
    EmailVerificationCode,
    EmailVerificationPurpose,
)
from ..models.user import User
from ..schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    SendEmailCodeResponse,
    AuthSessionResponse,
    UserResponse,
)
from .email_service import send_verification_email


logger = logging.getLogger(__name__)


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


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _generate_numeric_code() -> str:
    upper_bound = 10**settings.email_code_length
    return f"{secrets.randbelow(upper_bound):0{settings.email_code_length}d}"


def send_register_email_code(
    db: Session,
    email: str,
    sent_ip: str | None = None,
) -> SendEmailCodeResponse:
    normalized_email = _normalize_email(email)
    existing_user = db.scalar(select(User).where(User.email == normalized_email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )

    now = datetime.now()
    active_code = db.scalar(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.email == normalized_email,
            EmailVerificationCode.purpose == EmailVerificationPurpose.register,
            EmailVerificationCode.is_used.is_(False),
            EmailVerificationCode.expires_at > now,
        )
        .order_by(EmailVerificationCode.created_at.desc())
    )
    if active_code is not None:
        retry_after = int((active_code.expires_at - now).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "A valid unused verification code already exists. "
                f"Please retry after {retry_after} seconds."
            ),
        )

    code = _generate_numeric_code()
    verification = EmailVerificationCode(
        email=normalized_email,
        purpose=EmailVerificationPurpose.register,
        code_hash=hash_password(code),
        expires_at=now + timedelta(minutes=settings.email_code_expire_minutes),
        sent_ip=sent_ip,
    )
    db.add(verification)

    try:
        send_verification_email(normalized_email, code)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to send verification email to %s", normalized_email)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send verification email: {exc}",
        ) from exc

    return SendEmailCodeResponse(
        message="Verification code sent",
        expires_in_seconds=settings.email_code_expire_minutes * 60,
    )


def _consume_register_code(db: Session, email: str, code: str) -> None:
    verification = db.scalar(
        select(EmailVerificationCode)
        .where(
            EmailVerificationCode.email == email,
            EmailVerificationCode.purpose == EmailVerificationPurpose.register,
            EmailVerificationCode.is_used.is_(False),
        )
        .order_by(EmailVerificationCode.created_at.desc())
    )
    if verification is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code not found",
        )

    now = datetime.now()
    if verification.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired",
        )

    if verification.verify_attempts >= settings.email_code_max_verify_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Verification attempts exceeded",
        )

    verification.verify_attempts += 1
    if not verify_password(code, verification.code_hash):
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )

    verification.is_used = True
    verification.used_at = now


def register_user(db: Session, payload: RegisterRequest) -> RegisterResponse:
    normalized_email = _normalize_email(str(payload.email))
    existing = db.scalar(
        select(User).where(
            (User.email == normalized_email)
            | (User.username == payload.username)
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username is already registered",
        )

    _consume_register_code(db, normalized_email, payload.verification_code)

    user = User(
        email=normalized_email,
        username=payload.username,
        nickname=payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return RegisterResponse(
        message="User registered successfully",
        user=UserResponse.model_validate(user),
    )


def login_user(db: Session, redis: Redis, email: str, password: str) -> IssuedTokens:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or user.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

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


def login_with_wechat_code(
    db: Session,
    redis: Redis,
    code: str,
    nickname: str | None = None,
) -> IssuedTokens:
    # Development stub: in production, exchange code with WeChat API for openid.
    openid = f"dev_openid_{code}"
    user = db.scalar(select(User).where(User.openid == openid))
    if user is None:
        user = User(
            email=f"{openid}@dev.local",
            username=openid,
            openid=openid,
            nickname=nickname,
        )
        db.add(user)
    elif nickname and not user.nickname:
        user.nickname = nickname
    db.commit()
    db.refresh(user)
    return _issue_and_store_tokens(redis, user)
