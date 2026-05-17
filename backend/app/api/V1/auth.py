from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, status
from pydantic import EmailStr
from redis import Redis
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...core.redis_client import get_redis
from ...core.security import get_current_user
from ...models.user import User
from ...schemas.auth import (
    AuthMessageResponse,
    AuthSessionResponse,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    SendEmailCodeRequest,
    SendEmailCodeResponse,
    UserResponse,
    WechatLoginRequest,
)
from ...services.auth_service import (
    login_user,
    login_with_wechat_code,
    logout_user,
    refresh_user_tokens,
    register_user,
    send_register_email_code,
    token_response,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    cookie_options = {
        "httponly": True,
        "secure": settings.auth_cookie_secure,
        "samesite": settings.auth_cookie_samesite,
        "domain": settings.auth_cookie_domain,
        "path": "/",
    }
    response.set_cookie(
        key=settings.access_token_cookie_name,
        value=access_token,
        max_age=settings.access_token_expire_minutes * 60,
        **cookie_options,
    )
    response.set_cookie(
        key=settings.refresh_token_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_expire_minutes * 60,
        **cookie_options,
    )


def _clear_auth_cookies(response: Response) -> None:
    cookie_options = {
        "secure": settings.auth_cookie_secure,
        "samesite": settings.auth_cookie_samesite,
        "domain": settings.auth_cookie_domain,
        "path": "/",
    }
    response.delete_cookie(settings.access_token_cookie_name, **cookie_options)
    response.delete_cookie(settings.refresh_token_cookie_name, **cookie_options)


@router.post("/email-code", response_model=SendEmailCodeResponse)
def send_email_code(
    request: Request,
    email: EmailStr | None = Query(default=None),
    payload: SendEmailCodeRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> SendEmailCodeResponse:
    target_email = email or (payload.email if payload else None)
    if target_email is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="email is required",
        )
    client_host = request.client.host if request.client else None
    return send_register_email_code(db, str(target_email), client_host)


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(
    payload: RegisterRequest | None = Body(default=None),
    email: EmailStr | None = Query(default=None),
    username: str | None = Query(default=None, min_length=2, max_length=64),
    password: str | None = Query(default=None, min_length=6, max_length=128),
    verification_code: str | None = Query(default=None, min_length=4, max_length=12),
    db: Session = Depends(get_db),
) -> RegisterResponse:
    register_payload = payload
    if register_payload is None:
        if not all([email, username, password, verification_code]):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="email, username, password and verification_code are required",
            )
        register_payload = RegisterRequest(
            email=email,
            username=username,
            password=password,
            verification_code=verification_code,
        )
    return register_user(db, register_payload)


@router.post("/login", response_model=AuthSessionResponse)
def login(
    response: Response,
    payload: LoginRequest | None = Body(default=None),
    email: EmailStr | None = Query(default=None),
    password: str | None = Query(default=None, min_length=6, max_length=128),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AuthSessionResponse:
    login_payload = payload
    if login_payload is None:
        if email is None or password is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="email and password are required",
            )
        login_payload = LoginRequest(email=email, password=password)
    tokens = login_user(db, redis, str(login_payload.email), login_payload.password)
    _set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return token_response(tokens)


@router.post("/refresh", response_model=AuthSessionResponse)
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AuthSessionResponse:
    cookie_refresh_token = request.cookies.get(settings.refresh_token_cookie_name)
    tokens = refresh_user_tokens(db, redis, cookie_refresh_token)
    _set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return token_response(tokens)


@router.post("/logout", response_model=AuthMessageResponse)
def logout(
    request: Request,
    response: Response,
    redis: Redis = Depends(get_redis),
) -> AuthMessageResponse:
    access_token = request.cookies.get(settings.access_token_cookie_name)
    refresh_token = request.cookies.get(settings.refresh_token_cookie_name)
    logout_user(redis, access_token=access_token, refresh_token=refresh_token)
    _clear_auth_cookies(response)
    return AuthMessageResponse(message="Logged out")


@router.post("/wechat-login", response_model=AuthSessionResponse)
def wechat_login(
    response: Response,
    payload: WechatLoginRequest | None = Body(default=None),
    code: str | None = Query(default=None, min_length=1, max_length=256),
    nickname: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AuthSessionResponse:
    wechat_payload = payload
    if wechat_payload is None:
        if code is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="code is required",
            )
        wechat_payload = WechatLoginRequest(code=code, nickname=nickname)
    tokens = login_with_wechat_code(
        db,
        redis,
        wechat_payload.code,
        wechat_payload.nickname,
    )
    _set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return token_response(tokens)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
