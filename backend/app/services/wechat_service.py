from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from fastapi import HTTPException, status

from ..core.config import settings


def exchange_code_for_session(code: str) -> dict[str, Any]:
    if not settings.wechat_app_id or not settings.wechat_app_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WECHAT_APP_ID and WECHAT_APP_SECRET must be configured",
        )

    query = urlencode(
        {
            "appid": settings.wechat_app_id,
            "secret": settings.wechat_app_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }
    )
    url = f"{settings.wechat_jscode2session_url}?{query}"
    try:
        with urlopen(url, timeout=10) as response:
            data = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to request WeChat jscode2session: {exc}",
        ) from exc

    import json

    payload = json.loads(data)
    if payload.get("errcode"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"WeChat login failed: {payload.get('errmsg', payload.get('errcode'))}",
        )
    if not payload.get("openid"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="WeChat response missing openid",
        )
    return payload
