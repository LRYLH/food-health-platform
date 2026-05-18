from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from redis import Redis
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...core.redis_client import get_redis
from ...schemas.auth import MockLoginRequest, WechatLoginRequest, WechatLoginResponse
from ...services.auth_service import login_with_mock_user, login_with_wechat_code


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/wechat-login", response_model=WechatLoginResponse, status_code=status.HTTP_200_OK)
def wechat_login(
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

    return WechatLoginResponse(
        access_token=tokens.access_token,
        is_new_user=tokens.is_new_user,
    )


@router.post("/mock-login", response_model=WechatLoginResponse, status_code=status.HTTP_200_OK)
def mock_login(
    payload: MockLoginRequest = Body(default_factory=MockLoginRequest),
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> WechatLoginResponse:
    if settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mock login is disabled in production",
        )

    tokens = login_with_mock_user(
        db=db,
        redis=redis,
        username=payload.username,
        nickname=payload.nickname,
    )
    return WechatLoginResponse(
        access_token=tokens.access_token,
        is_new_user=tokens.is_new_user,
    )
