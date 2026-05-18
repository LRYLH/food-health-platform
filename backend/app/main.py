from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.V1 import admin, analyze, auth, profile
from .core.config import settings
from .core.database import init_db
from .core.response import validation_error_response


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.vision_input_dir.mkdir(parents=True, exist_ok=True)
    settings.vision_output_dir.mkdir(parents=True, exist_ok=True)
    settings.rag_input_dir.mkdir(parents=True, exist_ok=True)
    settings.rag_output_dir.mkdir(parents=True, exist_ok=True)
    settings.knowledge_upload_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


app.add_exception_handler(RequestValidationError, validation_error_response)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(analyze.router)
app.include_router(admin.router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
