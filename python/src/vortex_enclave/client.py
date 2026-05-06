"""Vortex Enclave client — sync (VortexClient) and async (AsyncVortexClient).

Both classes hide the JSON-RPC envelope and tool-name details. You call
`client.query(...)` and get back a typed `QueryResponse`.
"""

from __future__ import annotations
import os
import uuid
from typing import Any, Callable, Iterable, List, Sequence

LocalEmbedder = Callable[[str], Sequence[float]]
"""Anything callable as ``embedder(text) -> Sequence[float]`` works.
The SDK runs it before sending so the server only sees vectors."""

import httpx

from .constants import EMBEDDING_DIMENSION
from .errors import VortexEmbeddingError, raise_for_jsonrpc_error
from .types import (
    Identity,
    QueryResult,
    QueryResponse,
    IngestResult,
    DocumentSummary,
    DocumentListResponse,
    DocumentChunk,
    DocumentChunks,
    OrgStats,
    LogEvent,
    LogResponse,
    LinkResult,
    ForgetResult,
)

DEFAULT_ENDPOINT = "https://pbwwuvheu3rhomks6owwjolkjq0lhlht.lambda-url.us-east-1.on.aws/mcp"
DEFAULT_TIMEOUT_S = 30.0
USER_AGENT = "vortex-enclave-python/0.1.0"


# ─────────────────────────────────────────────────────────────────────────────
# JSON-RPC plumbing — shared by sync + async paths
# ─────────────────────────────────────────────────────────────────────────────


def _build_request(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
    }
    if params is not None:
        payload["params"] = params
    return payload


def _build_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    return _build_request("tools/call", {"name": name, "arguments": args})


def _unwrap_response(resp: dict[str, Any]) -> dict[str, Any]:
    if "error" in resp and resp["error"] is not None:
        raise_for_jsonrpc_error(resp["error"])
    result = resp.get("result")
    if result is None:
        return {}
    return result


def _unwrap_tool_call(resp: dict[str, Any]) -> dict[str, Any]:
    """tools/call wraps results in {content: [...], structuredContent: ...}.
    Return the structured payload."""
    result = _unwrap_response(resp)
    if "structuredContent" in result:
        return result["structuredContent"]
    return result


def _validate_vector(vec: List[float]) -> None:
    """Refuse to send vectors that obviously can't match the upstream index."""
    if len(vec) != EMBEDDING_DIMENSION:
        raise VortexEmbeddingError(
            f"Vector has {len(vec)} dimensions; upstream index expects "
            f"{EMBEDDING_DIMENSION}. Make sure your embedder produces "
            f"{EMBEDDING_DIMENSION}-dim mxbai-compatible vectors."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Sync client
# ─────────────────────────────────────────────────────────────────────────────


class VortexClient:
    """Synchronous Vortex Enclave client.

    Args:
        api_key: MCP key (falls back to VORTEX_API_KEY env var).
        endpoint: Override the hosted /mcp endpoint (for self-hosted deployments).
        timeout: HTTP timeout in seconds (default 30).
        http: Optional pre-configured httpx.Client (lets you set proxies, etc).
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        endpoint: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        http: httpx.Client | None = None,
        local_embedder: LocalEmbedder | None = None,
    ):
        self._api_key = api_key or os.environ.get("VORTEX_API_KEY")
        if not self._api_key:
            raise ValueError(
                "api_key is required (pass to constructor or set VORTEX_API_KEY env var)"
            )
        self._endpoint = endpoint or os.environ.get("VORTEX_MCP_ENDPOINT", DEFAULT_ENDPOINT)
        self._owns_http = http is None
        self._http = http or httpx.Client(timeout=timeout)
        self._local_embedder = local_embedder

    def __enter__(self) -> "VortexClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        r = self._http.post(
            self._endpoint,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-MCP-Key": self._api_key,
                "User-Agent": USER_AGENT,
            },
        )
        if r.status_code >= 500:
            r.raise_for_status()
        return r.json()

    # ── identity ─────────────────────────────────────────────────────────────

    def whoami(self) -> Identity:
        """Return the authenticated identity, role, and scopes."""
        resp = self._post(_build_call("vortex_whoami", {}))
        d = _unwrap_tool_call(resp)
        return Identity(**{k: d[k] for k in ("org_id", "user_id", "role", "type", "scopes")})

    # ── ingest ───────────────────────────────────────────────────────────────

    def ingest_text(
        self,
        text: str,
        *,
        title: str | None = None,
        doc_id: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> IngestResult:
        """Ingest text into the org's persistent memory. Returns a doc_id;
        embedding happens asynchronously and typically completes in ~10s."""
        args: dict[str, Any] = {"text": text}
        if title is not None:
            args["title"] = title
        if doc_id is not None:
            args["doc_id"] = doc_id
        if tags is not None:
            args["tags"] = tags
        d = _unwrap_tool_call(self._post(_build_call("vortex_ingest_text", args)))
        return IngestResult(**{k: d[k] for k in ("doc_id", "status", "estimated_seconds", "source_uri")})

    def ingest_url(
        self,
        url: str,
        *,
        doc_id: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> IngestResult:
        """Fetch a URL server-side and ingest its text body (≤5MB, 8s timeout)."""
        args: dict[str, Any] = {"url": url}
        if doc_id is not None:
            args["doc_id"] = doc_id
        if tags is not None:
            args["tags"] = tags
        d = _unwrap_tool_call(self._post(_build_call("vortex_ingest_url", args)))
        return IngestResult(**{k: d[k] for k in ("doc_id", "status", "estimated_seconds", "source_uri")})

    # ── browse ───────────────────────────────────────────────────────────────

    def list_documents(self, *, limit: int = 50) -> DocumentListResponse:
        """Enumerate doc_ids in the org's index, sorted by recency."""
        d = _unwrap_tool_call(self._post(_build_call("vortex_list_documents", {"limit": limit})))
        return DocumentListResponse(
            documents=[DocumentSummary(**doc) for doc in d.get("documents", [])],
            count=d["count"],
            scanned=d["scanned"],
            truncated=d["truncated"],
        )

    def get_document(self, doc_id: str) -> DocumentChunks:
        """Fetch all chunks for a doc_id, ordered by chunk_idx."""
        d = _unwrap_tool_call(self._post(_build_call("vortex_get_document", {"doc_id": doc_id})))
        return DocumentChunks(
            doc_id=d["doc_id"],
            chunks=[DocumentChunk(**c) for c in d.get("chunks", [])],
            count=d["count"],
        )

    # ── recall ───────────────────────────────────────────────────────────────

    def query(
        self,
        text_or_vector: str | Sequence[float],
        *,
        top_k: int = 10,
        expand: bool = True,
    ) -> QueryResponse:
        """Semantic search. Three modes:

        1. **Server-side embed** (default): pass text, server embeds with
           ``mxbai-embed-large-v1`` via the worker tunnel. Requires
           ``VORTEX_EMBED_URL`` set on the proxy Lambda.
        2. **Client-side embed**: pass text, the SDK runs your configured
           ``local_embedder`` and sends a vector. Query text never leaves your
           machine.
        3. **Pre-computed vector**: pass a 1024-dim list/tuple of floats.

        Returns top_k seeds plus graph-expanded neighbors (set expand=False
        to disable expansion).
        """
        args = self._build_query_args(text_or_vector, top_k, expand)
        d = _unwrap_tool_call(self._post(_build_call("vortex_query", args)))
        return QueryResponse(
            results=[QueryResult(**r) for r in d.get("results", [])],
            count=d["count"],
            org_id=d["org_id"],
        )

    def _build_query_args(
        self,
        text_or_vector: str | Sequence[float],
        top_k: int,
        expand: bool,
    ) -> dict[str, Any]:
        args: dict[str, Any] = {"top_k": top_k, "expand": expand}
        if isinstance(text_or_vector, str):
            if self._local_embedder is not None:
                vec = list(self._local_embedder(text_or_vector))
                _validate_vector(vec)
                args["vector"] = vec
            else:
                args["text"] = text_or_vector
        else:
            vec = list(text_or_vector)
            _validate_vector(vec)
            args["vector"] = vec
        return args

    # ── curation ─────────────────────────────────────────────────────────────

    def link(self, from_key: str, to_key: str, *, kind: str | None = None) -> LinkResult:
        """Author an explicit edge between two chunks (Karpathy-wiki-style)."""
        args: dict[str, Any] = {"from_key": from_key, "to_key": to_key}
        if kind is not None:
            args["kind"] = kind
        d = _unwrap_tool_call(self._post(_build_call("vortex_link", args)))
        return LinkResult(
            from_key=d["from_key"],
            to_key=d["to_key"],
            status=d["status"],
            edges=d.get("edges", []),
        )

    def log(
        self,
        *,
        since: int | None = None,
        limit: int = 50,
        kind: str | None = None,
    ) -> LogResponse:
        """Read recent activity events for the org. Newest-first."""
        args: dict[str, Any] = {"limit": limit}
        if since is not None:
            args["since"] = since
        if kind is not None:
            args["kind"] = kind
        d = _unwrap_tool_call(self._post(_build_call("vortex_log", args)))
        return LogResponse(
            org_id=d["org_id"],
            events=[LogEvent(**ev) for ev in d.get("events", [])],
            count=d["count"],
            since=d["since"],
        )

    def forget(self, doc_id: str) -> ForgetResult:
        """Delete every chunk for a doc_id, plus the raw S3 upload if present."""
        d = _unwrap_tool_call(self._post(_build_call("vortex_forget", {"doc_id": doc_id})))
        return ForgetResult(
            doc_id=d["doc_id"],
            deleted_chunks=d["deleted_chunks"],
            raw_object_dropped=d["raw_object_dropped"],
            raw_object_error=d.get("raw_object_error"),
        )

    # ── reflect ──────────────────────────────────────────────────────────────

    def stats(self) -> OrgStats:
        """High-level overview of the org's memory."""
        d = _unwrap_tool_call(self._post(_build_call("vortex_stats", {})))
        return OrgStats(**{k: d[k] for k in (
            "org_id", "total_chunks", "total_documents",
            "oldest_ingest_ts", "newest_ingest_ts",
            "scanned", "truncated", "text_embedding",
        )})


# ─────────────────────────────────────────────────────────────────────────────
# Async client — same interface, awaitable
# ─────────────────────────────────────────────────────────────────────────────


class AsyncVortexClient:
    """Async Vortex Enclave client. Same interface as VortexClient but every
    method is a coroutine. Use as `async with` for proper cleanup."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        endpoint: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        http: httpx.AsyncClient | None = None,
        local_embedder: LocalEmbedder | None = None,
    ):
        self._api_key = api_key or os.environ.get("VORTEX_API_KEY")
        if not self._api_key:
            raise ValueError(
                "api_key is required (pass to constructor or set VORTEX_API_KEY env var)"
            )
        self._endpoint = endpoint or os.environ.get("VORTEX_MCP_ENDPOINT", DEFAULT_ENDPOINT)
        self._owns_http = http is None
        self._http = http or httpx.AsyncClient(timeout=timeout)
        self._local_embedder = local_embedder

    async def __aenter__(self) -> "AsyncVortexClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        r = await self._http.post(
            self._endpoint,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-MCP-Key": self._api_key,
                "User-Agent": USER_AGENT,
            },
        )
        if r.status_code >= 500:
            r.raise_for_status()
        return r.json()

    async def whoami(self) -> Identity:
        d = _unwrap_tool_call(await self._post(_build_call("vortex_whoami", {})))
        return Identity(**{k: d[k] for k in ("org_id", "user_id", "role", "type", "scopes")})

    async def ingest_text(
        self, text: str, *,
        title: str | None = None, doc_id: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> IngestResult:
        args: dict[str, Any] = {"text": text}
        if title is not None: args["title"] = title
        if doc_id is not None: args["doc_id"] = doc_id
        if tags is not None: args["tags"] = tags
        d = _unwrap_tool_call(await self._post(_build_call("vortex_ingest_text", args)))
        return IngestResult(**{k: d[k] for k in ("doc_id", "status", "estimated_seconds", "source_uri")})

    async def ingest_url(
        self, url: str, *,
        doc_id: str | None = None, tags: dict[str, str] | None = None,
    ) -> IngestResult:
        args: dict[str, Any] = {"url": url}
        if doc_id is not None: args["doc_id"] = doc_id
        if tags is not None: args["tags"] = tags
        d = _unwrap_tool_call(await self._post(_build_call("vortex_ingest_url", args)))
        return IngestResult(**{k: d[k] for k in ("doc_id", "status", "estimated_seconds", "source_uri")})

    async def list_documents(self, *, limit: int = 50) -> DocumentListResponse:
        d = _unwrap_tool_call(await self._post(_build_call("vortex_list_documents", {"limit": limit})))
        return DocumentListResponse(
            documents=[DocumentSummary(**doc) for doc in d.get("documents", [])],
            count=d["count"], scanned=d["scanned"], truncated=d["truncated"],
        )

    async def get_document(self, doc_id: str) -> DocumentChunks:
        d = _unwrap_tool_call(await self._post(_build_call("vortex_get_document", {"doc_id": doc_id})))
        return DocumentChunks(
            doc_id=d["doc_id"],
            chunks=[DocumentChunk(**c) for c in d.get("chunks", [])],
            count=d["count"],
        )

    async def query(
        self, text_or_vector: str | Sequence[float], *,
        top_k: int = 10, expand: bool = True,
    ) -> QueryResponse:
        """Same three modes as VortexClient.query. See that docstring."""
        args: dict[str, Any] = {"top_k": top_k, "expand": expand}
        if isinstance(text_or_vector, str):
            if self._local_embedder is not None:
                vec = list(self._local_embedder(text_or_vector))
                _validate_vector(vec)
                args["vector"] = vec
            else:
                args["text"] = text_or_vector
        else:
            vec = list(text_or_vector)
            _validate_vector(vec)
            args["vector"] = vec
        d = _unwrap_tool_call(await self._post(_build_call("vortex_query", args)))
        return QueryResponse(
            results=[QueryResult(**r) for r in d.get("results", [])],
            count=d["count"], org_id=d["org_id"],
        )

    async def link(self, from_key: str, to_key: str, *, kind: str | None = None) -> LinkResult:
        args: dict[str, Any] = {"from_key": from_key, "to_key": to_key}
        if kind is not None: args["kind"] = kind
        d = _unwrap_tool_call(await self._post(_build_call("vortex_link", args)))
        return LinkResult(
            from_key=d["from_key"], to_key=d["to_key"], status=d["status"],
            edges=d.get("edges", []),
        )

    async def log(
        self, *, since: int | None = None,
        limit: int = 50, kind: str | None = None,
    ) -> LogResponse:
        args: dict[str, Any] = {"limit": limit}
        if since is not None: args["since"] = since
        if kind is not None: args["kind"] = kind
        d = _unwrap_tool_call(await self._post(_build_call("vortex_log", args)))
        return LogResponse(
            org_id=d["org_id"],
            events=[LogEvent(**ev) for ev in d.get("events", [])],
            count=d["count"], since=d["since"],
        )

    async def forget(self, doc_id: str) -> ForgetResult:
        d = _unwrap_tool_call(await self._post(_build_call("vortex_forget", {"doc_id": doc_id})))
        return ForgetResult(
            doc_id=d["doc_id"], deleted_chunks=d["deleted_chunks"],
            raw_object_dropped=d["raw_object_dropped"],
            raw_object_error=d.get("raw_object_error"),
        )

    async def stats(self) -> OrgStats:
        d = _unwrap_tool_call(await self._post(_build_call("vortex_stats", {})))
        return OrgStats(**{k: d[k] for k in (
            "org_id", "total_chunks", "total_documents",
            "oldest_ingest_ts", "newest_ingest_ts",
            "scanned", "truncated", "text_embedding",
        )})
