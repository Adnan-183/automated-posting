"""FastAPI entry point.

Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 4000
"""

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.platforms import build_platforms
from app.schemas import (
    FieldError,
    PostingResponse,
    PostRequest,
    ValidationErrorResponse,
)
from app.services.posting_service import PostingService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
# httpx logs every request URL at INFO; the Telegram URL contains the bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

app = FastAPI(
    title="Automated Multi-Platform Posting System",
    description=(
        "Publishes a short message with one CTA link to several third-party "
        "platforms through their official APIs, and reports the result for each."
    ),
    version="1.0.0",
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", ()) if part != "body"]
        message = error.get("msg", "Invalid value.").removeprefix("Value error, ")
        details.append(FieldError(field=".".join(location) or "body", message=message))
    body = ValidationErrorResponse(details=details)
    return JSONResponse(status_code=422, content=body.model_dump())


def get_posting_service(settings: Settings = Depends(get_settings)) -> PostingService:
    return PostingService(build_platforms(settings), settings.http_timeout_seconds)


@app.post(
    "/posting",
    response_model=PostingResponse,
    responses={422: {"model": ValidationErrorResponse, "description": "Invalid message"}},
    summary="Publish a message to every supported platform",
)
async def create_posting(
    payload: PostRequest,
    service: PostingService = Depends(get_posting_service),
) -> PostingResponse:
    return await service.publish(payload.message, payload.cta_url)


class PlatformStatus(BaseModel):
    platform: str
    configured: bool
    missing_env_vars: list[str]


@app.get("/platforms", response_model=list[PlatformStatus], summary="Show which platforms are configured")
async def list_platforms(settings: Settings = Depends(get_settings)) -> list[PlatformStatus]:
    statuses = []
    for platform in build_platforms(settings):
        missing = platform.missing_settings()
        statuses.append(
            PlatformStatus(platform=platform.name, configured=not missing, missing_env_vars=missing)
        )
    return statuses


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health", summary="Health check")
async def health() -> dict:
    return {"status": "ok"}
