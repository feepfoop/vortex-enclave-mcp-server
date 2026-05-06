"""Typed result objects returned by VortexClient methods.

Using dataclasses (not Pydantic) to keep the dependency footprint minimal —
this library has exactly one runtime dep (httpx). If you want stricter
validation, layer Pydantic on top of these dataclasses on your side.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Identity:
    """Returned by `client.whoami()`."""

    org_id: str
    user_id: str
    role: str  # "admin" | "editor" | "viewer"
    type: str  # "api" | "mcp"
    scopes: list[str]


@dataclass
class QueryResult:
    """A single chunk returned from a query."""

    key: str
    distance: float
    hop: int  # 0 = seed, 1 = pulled in via graph expansion
    metadata: dict[str, Any]


@dataclass
class QueryResponse:
    """Returned by `client.query(...)`."""

    results: list[QueryResult]
    count: int
    org_id: str


@dataclass
class IngestResult:
    """Returned by `client.ingest_text(...)` and `client.ingest_url(...)`."""

    doc_id: str
    status: str  # "queued"
    estimated_seconds: int
    source_uri: str


@dataclass
class DocumentSummary:
    """One row in `client.list_documents()` output."""

    doc_id: str
    chunk_count: int
    ingested_at: int  # unix epoch seconds; 0 if unknown


@dataclass
class DocumentListResponse:
    documents: list[DocumentSummary]
    count: int
    scanned: int
    truncated: bool


@dataclass
class DocumentChunk:
    key: str
    metadata: dict[str, Any]


@dataclass
class DocumentChunks:
    """Returned by `client.get_document(doc_id)`."""

    doc_id: str
    chunks: list[DocumentChunk]
    count: int


@dataclass
class OrgStats:
    """Returned by `client.stats()`."""

    org_id: str
    total_chunks: int
    total_documents: int
    oldest_ingest_ts: int
    newest_ingest_ts: int
    scanned: int
    truncated: bool
    text_embedding: bool  # whether server-side text→vector embedding is configured


@dataclass
class LogEvent:
    """One row in `client.log()` output."""

    ts: int  # epoch milliseconds
    kind: str  # "ingest_text" | "ingest_url" | "forget" | "link" | ...
    user_id: str | None = None
    doc_id: str | None = None
    key_hash: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class LogResponse:
    org_id: str
    events: list[LogEvent]
    count: int
    since: int


@dataclass
class LinkResult:
    """Returned by `client.link(from_key, to_key)`."""

    from_key: str
    to_key: str
    status: str  # "linked" | "already_linked"
    edges: list[str] = field(default_factory=list)


@dataclass
class ForgetResult:
    """Returned by `client.forget(doc_id)`."""

    doc_id: str
    deleted_chunks: int
    raw_object_dropped: bool
    raw_object_error: str | None = None
