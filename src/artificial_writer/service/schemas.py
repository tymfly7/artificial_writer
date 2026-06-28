"""Pydantic request/response models shared by the web front-end and the API.

These were originally defined inline in ``web/app.py``; they live here now so the
service layer and the web routers share one source of truth.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from ..core.config import SummarizerType
from ..core.output_format import OutputFormat

# --- Summarize / fetch (moved from web/app.py) -----------------------------------


class SummarizeRequest(BaseModel):
    url: HttpUrl
    summarizer: SummarizerType | None = None
    model: str | None = None  # local model name (Ollama); ignored by other backends
    output_format: OutputFormat | None = None


class SummarizeResponse(BaseModel):
    title: str
    url: str
    backend: str
    model: str | None
    elapsed_seconds: float
    summary: str


class FetchRequest(BaseModel):
    url: HttpUrl


class FetchResponse(BaseModel):
    title: str
    url: str
    word_count: int
    text: str


# --- Auth ------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class ApiKeyResponse(BaseModel):
    """An API key. ``key`` is populated only when a key is first issued."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prefix: str
    created_at: datetime
    revoked_at: datetime | None = None
    key: str | None = None  # full secret, returned exactly once on creation


class AccountResponse(BaseModel):
    """The signed-in user's profile alongside today's usage and tier caps."""

    id: uuid.UUID
    email: str
    tier: str
    created_at: datetime
    requests_today: int
    cost_usd_today: float
    daily_request_cap: int
    daily_cost_cap_usd: float


class EmailChangeRequest(BaseModel):
    """Changing the login email re-confirms the current password."""

    new_email: str
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class AccountDeleteRequest(BaseModel):
    """Deleting an account is irreversible, so re-confirm the password."""

    password: str


# --- Archive ---------------------------------------------------------------------


class SummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_url: str
    source_type: str
    title: str
    summary: str
    output_format: str
    backend: str
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    created_at: datetime


class ArchiveQuery(BaseModel):
    q: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


# --- Batch jobs ------------------------------------------------------------------


class BatchRequest(BaseModel):
    urls: list[HttpUrl] = Field(min_length=1)
    output_format: OutputFormat | None = None
    summarizer: SummarizerType | None = None
    model: str | None = None


class JobOut(BaseModel):
    """The id/status of an enqueued batch job; ``digest_id`` once finished."""

    job_id: str
    status: str | None = None
    digest_id: str | None = None


# --- Feeds -----------------------------------------------------------------------


class FeedCreate(BaseModel):
    rss_url: HttpUrl
    cadence_minutes: int = Field(ge=1)


class FeedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rss_url: str
    cadence_minutes: int
    last_polled: datetime | None
    created_at: datetime


# --- Digests ---------------------------------------------------------------------


class DigestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    body: str
    summary_ids: list[str]
    created_at: datetime
