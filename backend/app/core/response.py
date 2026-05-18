from datetime import UTC, datetime
import json
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import StreamingResponse


SKIP_RESPONSE_WRAP_PATHS = {
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}


def current_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_response(
    *,
    code: str,
    msg: str,
    data: Any,
) -> dict[str, Any]:
    return {
        "code": code,
        "msg": msg,
        "data": data,
        "timestamp": current_timestamp(),
    }


def success_response(data: Any = None, msg: str = "success") -> dict[str, Any]:
    return build_response(code="0", msg=msg, data=data)


def error_response(code: str, msg: str, data: Any = None) -> dict[str, Any]:
    return build_response(code=code, msg=msg, data=data)


class UnifiedResponseMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if not settings_compatible_response_wrap_enabled():
            return await call_next(request)

        response = await call_next(request)
        if request.url.path in SKIP_RESPONSE_WRAP_PATHS:
            return response

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response
        if isinstance(response, StreamingResponse):
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
        else:
            return response

        if not body:
            data = None
        else:
            data = json.loads(body.decode("utf-8"))

        if isinstance(data, dict) and {"code", "msg", "data", "timestamp"} <= data.keys():
            wrapped = data
        else:
            wrapped = success_response(data=data)

        headers = dict(response.headers)
        headers.pop("content-length", None)
        return JSONResponse(
            status_code=response.status_code,
            content=wrapped,
            headers=headers,
            background=response.background,
        )


def settings_compatible_response_wrap_enabled() -> bool:
    from .config import settings

    return settings.response_envelope_enabled


def validation_error_response(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    if not settings_compatible_response_wrap_enabled():
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )

    return JSONResponse(
        status_code=422,
        content=error_response(
            code="VALIDATION_ERROR",
            msg="Validation error",
            data=exc.errors(),
        ),
    )
