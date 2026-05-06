"""Vortex Enclave — native Python client.

Quickstart::

    from vortex_enclave import VortexClient

    with VortexClient(api_key="mcp_xxx") as client:
        doc = client.ingest_text("Notes on chunking strategies", title="rag-notes")
        results = client.query("how do I split documents?", top_k=5)
        for r in results.results:
            print(r.metadata.get("text", "")[:80])

Or async::

    import asyncio
    from vortex_enclave import AsyncVortexClient

    async def main():
        async with AsyncVortexClient(api_key="mcp_xxx") as client:
            results = await client.query("how do I split documents?")

    asyncio.run(main())
"""

from .client import VortexClient, AsyncVortexClient
from .errors import (
    VortexError,
    VortexAuthError,
    VortexScopeError,
    VortexInvalidParamsError,
    VortexInternalError,
)
from .types import (
    QueryResult,
    QueryResponse,
    IngestResult,
    DocumentSummary,
    DocumentListResponse,
    DocumentChunks,
    OrgStats,
    LogEvent,
    LogResponse,
    LinkResult,
    Identity,
    ForgetResult,
)

__version__ = "0.1.0"

__all__ = [
    "VortexClient",
    "AsyncVortexClient",
    "VortexError",
    "VortexAuthError",
    "VortexScopeError",
    "VortexInvalidParamsError",
    "VortexInternalError",
    "QueryResult",
    "QueryResponse",
    "IngestResult",
    "DocumentSummary",
    "DocumentListResponse",
    "DocumentChunks",
    "OrgStats",
    "LogEvent",
    "LogResponse",
    "LinkResult",
    "Identity",
    "ForgetResult",
]
