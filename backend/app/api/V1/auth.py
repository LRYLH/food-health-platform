from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from redis import Redis
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...core.redis_client import get_redis
from ...schemas.auth import WechatLoginRequest, WechatLoginResponse
from ...services.auth_service import login_with_wechat_code


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


@router.post("/wechat-login", response_model=WechatLoginResponse, status_code=status.HTTP_200_OK)
def wechat_login(
    response: Response,
    payload: WechatLoginRequest | None = Body(default=None),
    code: str | None = Query(default=None, min_length=1, max_length=256),
    nickname: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> WechatLoginResponse:
    if payload is None and code is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="code is required",
        )
    request_payload = payload or WechatLoginRequest(code=code or "", nickname=nickname)
    tokens = login_with_wechat_code(
        db,
        redis,
        request_payload.code,
        request_payload.nickname,
    )

    _set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return WechatLoginResponse(
        access_token=tokens.access_token,
        is_new_user=tokens.is_new_user,
    )
