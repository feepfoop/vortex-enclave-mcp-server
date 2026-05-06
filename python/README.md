# vortex-enclave (Python)

Native Python client for [Vortex Enclave](https://fusionlab.ai) — sovereign
vector search and agent memory backed by AWS S3 Vectors.

Talks to the hosted `/mcp` endpoint over HTTPS, hides the JSON-RPC envelope,
returns dataclass-typed results. Sync (`VortexClient`) and async
(`AsyncVortexClient`) variants share the same interface.

## Install

```bash
pip install vortex-enclave   # once published
```

Until then, install directly from this repo:

```bash
pip install "git+https://github.com/feepfoop/vortex-enclave-mcp-server.git#subdirectory=python"
```

## Quickstart

```python
import os
from vortex_enclave import VortexClient

os.environ["VORTEX_API_KEY"] = "mcp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

with VortexClient() as client:
    # Remember something
    doc = client.ingest_text(
        "Vortex Enclave uses mxbai-embed-large-v1 for embeddings.",
        title="model-notes",
    )
    print(f"queued doc_id={doc.doc_id}")

    # Recall it (text input — server embeds via the worker tunnel)
    results = client.query("which embedding model do we use?", top_k=5)
    for r in results.results:
        text = r.metadata.get("text", "")[:80]
        print(f"  {r.key}  d={r.distance:.3f}  hop={r.hop}  {text!r}")

    # Or recall with a pre-computed 1024-dim vector
    # results = client.query([0.0123, -0.0456, ...], top_k=5)
```

## Async usage

```python
import asyncio
from vortex_enclave import AsyncVortexClient

async def main():
    async with AsyncVortexClient(api_key="mcp_xxx") as client:
        results = await client.query("how do I split documents?", top_k=10)
        for r in results.results:
            print(r.key, r.distance)

asyncio.run(main())
```

## Methods

All ten MCP tools, exposed as native methods. `VortexClient` and
`AsyncVortexClient` share the same names.

| Method | Returns | Required scope |
|---|---|---|
| `whoami()` | `Identity` | (any) |
| `query(text_or_vector, top_k=10, expand=True)` | `QueryResponse` | `query` |
| `ingest_text(text, title=, doc_id=, tags=)` | `IngestResult` | `ingest` |
| `ingest_url(url, doc_id=, tags=)` | `IngestResult` | `ingest` |
| `list_documents(limit=50)` | `DocumentListResponse` | `query` |
| `get_document(doc_id)` | `DocumentChunks` | `query` |
| `link(from_key, to_key, kind=)` | `LinkResult` | `ingest` |
| `forget(doc_id)` | `ForgetResult` | `ingest` |
| `stats()` | `OrgStats` | `query` |
| `log(since=, limit=50, kind=)` | `LogResponse` | `query` |

Each method returns a `dataclass` — autocomplete, type-check, JSON-encode it.
See `vortex_enclave/types.py` for full field definitions.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `VORTEX_API_KEY` | — | Required. MCP key from the portal. |
| `VORTEX_MCP_ENDPOINT` | hosted `/mcp` URL | Override for self-hosted. |

Or pass `api_key=` and `endpoint=` to the constructor:

```python
client = VortexClient(
    api_key="mcp_...",
    endpoint="https://your-self-hosted.example.com/mcp",
    timeout=60.0,
)
```

## Errors

```python
from vortex_enclave import (
    VortexAuthError,         # bad / missing API key
    VortexScopeError,        # key lacks the scope for the tool
    VortexInvalidParamsError, # bad args
    VortexInternalError,     # server-side failure
    VortexError,             # parent class
)

try:
    client.ingest_text("hi")
except VortexScopeError as e:
    # e.data has {tool, required_scope, granted_scopes, role}
    print(f"need {e.data['required_scope']} scope; have {e.data['granted_scopes']}")
```

All errors inherit from `VortexError`.

## License

MIT — see [../LICENSE](../LICENSE).
