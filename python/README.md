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

    # Recall it (server embeds the text — see "Embedding modes" below)
    results = client.query("which embedding model do we use?", top_k=5)
    for r in results.results:
        text = r.metadata.get("text", "")[:80]
        print(f"  {r.key}  d={r.distance:.3f}  hop={r.hop}  {text!r}")
```

## Embedding modes — three ways to query

The upstream index is built with **`mixedbread-ai/mxbai-embed-large-v1`**
(1024-dim, cosine, L2-normalized). All vectors must come from this exact
embedding space. The SDK exposes the constants if you need them:

```python
from vortex_enclave import EMBEDDING_MODEL, EMBEDDING_DIMENSION
# → "mixedbread-ai/mxbai-embed-large-v1", 1024
```

### Mode 1 — server-side embed (default, easiest)

Pass text. The server embeds via the worker tunnel and runs the search.
Requires `VORTEX_EMBED_URL` to be set on the proxy Lambda (one-time
deployment setup).

```python
results = client.query("how does chunking work?", top_k=5)
```

Pros: zero local setup. Cons: query text crosses the network.

### Mode 2 — client-side embed (recommended for privacy or scale)

Pass text + give the SDK a local embedder. The SDK runs your embedder
client-side and sends only the resulting vector. Query text never leaves
your machine.

```python
# Install the bundled mxbai helper:  pip install 'vortex-enclave[mxbai]'
from vortex_enclave import VortexClient
from vortex_enclave.embedders import MxbaiEmbedder

embedder = MxbaiEmbedder()  # auto-detects CUDA → MPS → CPU
with VortexClient(local_embedder=embedder) as client:
    results = client.query("how does chunking work?", top_k=5)
```

Or bring your own callable — anything `(text: str) -> Sequence[float]`
where the output is a 1024-dim L2-normalized mxbai-compatible vector:

```python
def my_embedder(text: str) -> list[float]:
    return some_mxbai_compatible_pipeline(text)

with VortexClient(local_embedder=my_embedder) as client:
    results = client.query("...")
```

The SDK validates the dimension before sending and raises
`VortexEmbeddingError` if the vector isn't 1024-dim.

### Mode 3 — pre-computed vectors (advanced)

Already have vectors from your own pipeline? Pass them directly:

```python
v = my_pipeline.embed(query_text)  # must be 1024-d, mxbai-space, L2-normed
results = client.query(v, top_k=5)
```

You're on the hook for embedding-space match. The SDK validates dimension;
it can't verify your model.

### Picking a mode

| Mode | Privacy | Setup | Latency | When |
|---|---|---|---|---|
| Server-side | text crosses wire | none | network round-trip | the default — fine for most things |
| Client-side (`MxbaiEmbedder`) | text stays local | `pip install '...[mxbai]'` | depends on your hardware | privacy-sensitive queries; offline-friendly |
| Pre-computed | text stays local | depends on you | fastest | bulk batches; integration with existing embed pipelines |

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
