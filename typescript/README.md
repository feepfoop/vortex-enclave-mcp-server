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

// Recall (text input — server embeds via the worker tunnel)
const results = await client.query("how do I split documents?", { topK: 5 });
for (const r of results.results) {
  const text = (r.metadata.text as string | undefined)?.slice(0, 80);
  console.log(`  ${r.key}  d=${r.distance.toFixed(3)}  hop=${r.hop}  ${text}`);
}
```

Or with a pre-computed 1024-dim vector:

```ts
const results = await client.query([0.0123, -0.0456, /* ... 1024 floats ... */]);
```

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
