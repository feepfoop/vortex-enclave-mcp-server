# @vortex-enclave/sdk (TypeScript / JavaScript)

Native TypeScript/JavaScript client for [Vortex Enclave](https://fusionlab.ai)
— sovereign vector search and agent memory backed by AWS S3 Vectors.

Talks to the hosted `/mcp` endpoint over HTTPS, hides the JSON-RPC envelope,
returns strongly-typed results. Works in **Node 20+** and **any modern
browser** (uses native `fetch`).

## Install

```bash
npm install @vortex-enclave/sdk    # once published
```

Until then, install directly from this repo:

```bash
npm install "git+https://github.com/feepfoop/vortex-enclave-mcp-server.git#main:typescript"
# or as a local file:
git clone https://github.com/feepfoop/vortex-enclave-mcp-server.git
cd vortex-enclave-mcp-server/typescript && npm install && npm run build
# then in your project:
npm install /path/to/vortex-enclave-mcp-server/typescript
```

## Quickstart

```ts
import { VortexClient } from "@vortex-enclave/sdk";

const client = new VortexClient({ apiKey: "mcp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" });

// Remember
const doc = await client.ingestText("Notes on chunking strategies", {
  title: "rag-notes",
});
console.log("queued", doc.doc_id);

// Recall (server embeds the text — see "Embedding modes" below)
const results = await client.query("how do I split documents?", { topK: 5 });
for (const r of results.results) {
  const text = (r.metadata.text as string | undefined)?.slice(0, 80);
  console.log(`  ${r.key}  d=${r.distance.toFixed(3)}  hop=${r.hop}  ${text}`);
}
```

## Embedding modes — three ways to query

The upstream index is built with **`mixedbread-ai/mxbai-embed-large-v1`**
(1024-dim, cosine, L2-normalized). All vectors must come from this exact
embedding space. The SDK exports the constants:

```ts
import { EMBEDDING_MODEL, EMBEDDING_DIMENSION } from "@vortex-enclave/sdk";
// → "mixedbread-ai/mxbai-embed-large-v1", 1024
```

### Mode 1 — server-side embed (default, easiest)

Pass text. The server embeds via the worker tunnel.

```ts
const results = await client.query("how does chunking work?", { topK: 5 });
```

### Mode 2 — client-side embed (recommended for privacy or scale)

Provide a `localEmbedder` to the constructor. The SDK runs it client-side
and sends only the resulting 1024-dim vector. Query text never leaves your
machine.

In Node, [`@xenova/transformers`](https://github.com/xenova/transformers.js)
runs mxbai locally via ONNX:

```ts
import { VortexClient } from "@vortex-enclave/sdk";
import { pipeline } from "@xenova/transformers";

// One-time: load the model (downloads ~700MB to local cache)
const embedder = await pipeline("feature-extraction", "mixedbread-ai/mxbai-embed-large-v1");

const client = new VortexClient({
  apiKey: process.env.VORTEX_API_KEY,
  localEmbedder: async (text) => {
    const out = await embedder(text, { pooling: "mean", normalize: true });
    return Array.from(out.data);
  },
});

const results = await client.query("how does chunking work?");
```

In a browser, the same approach works — `@xenova/transformers` is
browser-compatible. Set `localEmbedder` and the query text never crosses
the network.

Or bring your own callable that returns a 1024-dim L2-normalized
mxbai-compatible vector:

```ts
const client = new VortexClient({
  apiKey: "...",
  localEmbedder: async (text: string) => {
    return await mySdkOfChoice.embed(text);  // must be 1024-d, mxbai-space
  },
});
```

The SDK validates the dimension before sending and throws
`VortexEmbeddingError` if it isn't 1024.

### Mode 3 — pre-computed vectors (advanced)

```ts
const v = await myPipeline.embed(queryText);  // must be 1024-d, mxbai-space
const results = await client.query(v, { topK: 5 });
```

### Picking a mode

| Mode | Privacy | Setup | Latency | When |
|---|---|---|---|---|
| Server-side | text crosses wire | none | network round-trip | the default — fine for most things |
| Client-side (`localEmbedder`) | text stays local | `npm i @xenova/transformers` | first run downloads model | privacy; offline-friendly; browser apps |
| Pre-computed | text stays local | depends on you | fastest | bulk batches; existing pipelines |

## Methods

All ten MCP tools, exposed as native methods.

| Method | Returns | Required scope |
|---|---|---|
| `whoami()` | `Identity` | (any) |
| `query(textOrVector, { topK?, expand? })` | `QueryResponse` | `query` |
| `ingestText(text, { title?, docId?, tags? })` | `IngestResult` | `ingest` |
| `ingestUrl(url, { docId?, tags? })` | `IngestResult` | `ingest` |
| `listDocuments(limit?)` | `DocumentListResponse` | `query` |
| `getDocument(docId)` | `DocumentChunks` | `query` |
| `link(fromKey, toKey, { kind? })` | `LinkResult` | `ingest` |
| `forget(docId)` | `ForgetResult` | `ingest` |
| `stats()` | `OrgStats` | `query` |
| `log({ since?, limit?, kind? })` | `LogResponse` | `query` |

All return types are exported from the package — full TS autocomplete +
type-checking in your editor.

## Configuration

Constructor options, all optional except `apiKey`:

```ts
new VortexClient({
  apiKey: "mcp_...",                                    // or VORTEX_API_KEY env (Node)
  endpoint: "https://your-self-hosted.example.com/mcp", // or VORTEX_MCP_ENDPOINT env
  timeoutMs: 30_000,
  fetchImpl: customFetch,                               // for testing/proxies
});
```

In Node, `VORTEX_API_KEY` and `VORTEX_MCP_ENDPOINT` env vars are read by
default. In the browser, you must pass `apiKey` explicitly (and be aware
that exposing an MCP key to client JS gives anyone with browser tools the
same access as your agent — generally a bad idea; use a server middleware
instead).

## Errors

```ts
import {
  VortexAuthError,           // bad / missing API key
  VortexScopeError,          // key lacks scope for the called tool
  VortexInvalidParamsError,  // bad args
  VortexInternalError,       // server-side failure
  VortexError,               // base class
} from "@vortex-enclave/sdk";

try {
  await client.ingestText("hi");
} catch (e) {
  if (e instanceof VortexScopeError) {
    // e.data has { tool, required_scope, granted_scopes, role }
    console.error(`need ${(e.data as any).required_scope}, have ${(e.data as any).granted_scopes}`);
  }
  throw e;
}
```

## License

MIT — see [../LICENSE](../LICENSE).
