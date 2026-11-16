"""Request and response models for the posting API."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.validation import MAX_MESSAGE_LENGTH, extract_links, validate_url

EXAMPLE_MESSAGE = (
    "Check out our latest business platform and grow your online visibility. "
    "https://example.com"
)


class PostRequest(BaseModel):
    # Extra fields are rejected: the caller cannot choose platforms,
    # platform selection is handled by the application.
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"message": EXAMPLE_MESSAGE}]},
    )

    message: str = Field(
        ...,
        description=(
            f"Text to publish. Max {MAX_MESSAGE_LENGTH} characters, "
            "must contain exactly one http(s) CTA link."
        ),
    )

    @field_validator("message")
    @classmethod
    def check_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message must not be empty.")
        if len(value) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message must not exceed {MAX_MESSAGE_LENGTH} characters (got {len(value)})."
            )

        links = extract_links(value)
        if not links:
            raise ValueError("Message must include exactly one CTA link (none found).")
        if len(links) > 1:
            raise ValueError(
                f"Message must include exactly one CTA link (found {len(links)}: "
                f"{', '.join(links)})."
            )

        validate_url(links[0])
        return value

    @property
    def cta_url(self) -> str:
        return extract_links(self.message)[0]


class PostStatus(str, Enum):
    success = "success"
    failed = "failed"


class PlatformResult(BaseModel):
    platform: str
    status: PostStatus
    posted_url: str | None = None
    public_access: bool = False
    date: str | None = Field(None, description="Posting date (UTC), YYYY-MM-DD.")
    time: str | None = Field(None, description="Posting time (UTC), HH:MM:SS.")
    error: str | None = None
    note: str | None = Field(
        None, description="Extra detail on a successful post, e.g. why it is not publicly accessible."
    )


class Summary(BaseModel):
    total: int
    succeeded: int
    failed: int


class PostingResponse(BaseModel):
    success: bool = Field(..., description="True when at least one platform succeeded.")
    message: str
    cta_url: str
    summary: Summary
    results: list[PlatformResult]


class FieldError(BaseModel):
    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    success: bool = False
    error: str = "validation_error"
    details: list[FieldError]
