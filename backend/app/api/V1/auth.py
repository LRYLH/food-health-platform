from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, status
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
    UserResponse,
    WechatLoginRequest,
)
from ...services.auth_service import (
    login_with_wechat_code,
    logout_user,
    refresh_user_tokens,
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


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
