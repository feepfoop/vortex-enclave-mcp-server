# Vortex Enclave — Clients

Public client packages for [Vortex Enclave](https://fusionlab.ai) — sovereign
vector search and agent memory backed by AWS S3 Vectors. Four integration
shapes ship from this repo:

| Package | Use when | Path |
|---|---|---|
| [`@vortex-enclave/mcp-server`](./bridge) | An MCP host (Claude Desktop, Cursor, Continue) needs to spawn a stdio bridge | [`bridge/`](./bridge) |
| [`vortex-enclave`](./python) (Python) | Native Python integration — you're calling Vortex from your own code | [`python/`](./python) |
| [`@vortex-enclave/sdk`](./typescript) (TypeScript / JavaScript) | Native TS/JS integration in Node 20+ or modern browsers | [`typescript/`](./typescript) |
| [`vortex-ingest-cli`](./helpers/ingest-cli) | One-shot: "I have a folder, get it queryable." Walks any directory, parses each file by type (PDF/DOCX/PPTX/HTML/code/text), uploads via the SDK. | [`helpers/ingest-cli/`](./helpers/ingest-cli) |

All four talk to the same upstream `/mcp` endpoint and authenticate via the
same MCP key minted in the portal. They differ only in how they're invoked.

## What the upstream server provides

Ten tools, in three categories:

| Category | Tools | Required scope |
|---|---|---|
| **Recall** | `vortex_query` (text or vector) | `query` |
| **Remember** | `vortex_ingest_text`, `vortex_ingest_url` | `ingest` |
| **Browse** | `vortex_list_documents`, `vortex_get_document` | `query` |
| **Curate** (Karpathy-wiki-pattern) | `vortex_link`, `vortex_log` | `ingest` / `query` |
| **Manage** | `vortex_forget` | `ingest` |
| **Reflect** | `vortex_whoami`, `vortex_stats` | (any) / `query` |

## Embedding model — what gets enforced and how

The upstream index is built with **`mxbai-embed-large-v1`** (Mixedbread AI),
1024-dim, cosine, L2-normalized. **Every vector — ingested or queried — must
live in this embedding space.** Mixing models silently returns nonsense:
cosine across mismatched embedding spaces is not meaningful, but it doesn't
error either, it just retrieves garbage with confidence.

What's enforced where:

| Layer | Check | When it fires |
|---|---|---|
| **Server-side ingest** (worker → S3 Vectors) | hardcoded to mxbai in worker | every chunk written |
| **Server-side query embedding** (`text` → vector via worker tunnel) | hardcoded to mxbai in worker `/embed` | every text-mode query when configured |
| **SDK / bridge: dimension check** | rejects non-1024-d vectors before sending | every pre-computed vector |
| **SDK: model attestation** | not implementable — a 1024-d float array carries no model identity | — |

So enforcement runs at three levels but the **honor system applies on the wire** — the server can't tell if your 1024-d vector came from mxbai or from a different model truncated to 1024. Use the `localEmbedder` hook (see below) and you don't have to think about it.

### Three query modes — pick by what your agent needs

| Mode | Where embedding runs | Query text leaves machine? | Setup |
|---|---|---|---|
| **Server-side** (default) | Worker tunnel via `VORTEX_EMBED_URL` | yes | none if the deployment has tunnel configured |
| **Client-side via `localEmbedder`** | Inside the SDK, before HTTPS | no | `pip install 'vortex-enclave[mxbai]'` (Python) / `npm i @xenova/transformers` (TS) |
| **Pre-computed vector** | Wherever you want | no | your problem to keep models aligned |

All three SDKs (Python, TS, plus the bridge) accept a vector as input. The Python and TS SDKs add a `local_embedder` / `localEmbedder` parameter that runs an embedder client-side automatically when you pass text — see each SDK's README for examples.

The bridge is a transparent JSON-RPC pipe. If your MCP host can compute embeddings before calling, send `vector` in your tool call and it'll pass through. Most MCP hosts don't embed locally, so they typically use server-side mode.

## Quick picker

**You're an AI host (Claude Desktop / Cursor / Continue):** use the
[bridge](./bridge). The MCP host spawns it as a subprocess, you paste a
config block.

**You're writing Python:** use the [Python SDK](./python).

```python
from vortex_enclave import VortexClient
with VortexClient(api_key="mcp_...") as client:
    results = client.query("how does chunking work?", top_k=5)
```

**You're writing TypeScript/JavaScript:** use the [TS SDK](./typescript).

```ts
import { VortexClient } from "@vortex-enclave/sdk";
const client = new VortexClient({ apiKey: "mcp_..." });
const results = await client.query("how does chunking work?", { topK: 5 });
```

## How auth works

All three packages send `X-MCP-Key: $VORTEX_API_KEY` (or `Authorization:
Bearer $VORTEX_API_KEY`) on every request. The upstream server SHA-256-hashes
the key, looks up SSM at `/vortex/keys/{hash}`, and resolves it to
`{org_id, role, scopes}`. Each tool call is RBAC-checked server-side.

Agents inherit the role of whoever minted the key, downgraded if the human
chose a stricter scope. A `viewer`-scoped key cannot call ingest tools
regardless of what the agent asks for.

## Mint a key

1. Sign in at <https://fusionlab.ai>
2. MCP Keys → Create Key → choose name + scope
3. Copy the `mcp_…` value (shown once only)
4. Paste into your client's config / env

## Repo layout

```
vortex-enclave-mcp-server/
├── bridge/                       # @vortex-enclave/mcp-server — stdio bridge (Node)
├── python/                       # vortex-enclave — Python SDK (sync + async)
├── typescript/                   # @vortex-enclave/sdk — TS/JS SDK
├── helpers/
│   └── ingest-cli/               # vortex-ingest — bulk directory uploader
├── README.md                     # you are here
└── LICENSE                       # MIT, applies to everything in this repo
```

The Vortex Enclave platform itself (AWS CDK, Go Lambda proxy, Next.js portal,
Python ingestion worker) lives in a separate private monorepo. This
repository contains only the client-facing pieces.

## License

MIT — see [LICENSE](./LICENSE). Each package's `README.md` has its own
quickstart and full API reference.
