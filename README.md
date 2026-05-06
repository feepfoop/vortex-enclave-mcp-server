# Vortex Enclave — Clients

Public client packages for [Vortex Enclave](https://fusionlab.ai) — sovereign
vector search and agent memory backed by AWS S3 Vectors. Three integration
shapes ship from this repo:

| Package | Use when | Path |
|---|---|---|
| [`@vortex-enclave/mcp-server`](./bridge) | An MCP host (Claude Desktop, Cursor, Continue) needs to spawn a stdio bridge | [`bridge/`](./bridge) |
| [`vortex-enclave`](./python) (Python) | Native Python integration — you're calling Vortex from your own code | [`python/`](./python) |
| [`@vortex-enclave/sdk`](./typescript) (TypeScript / JavaScript) | Native TS/JS integration in Node 20+ or modern browsers | [`typescript/`](./typescript) |

All three talk to the same upstream `/mcp` endpoint and authenticate via the
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

## Embedding model

The upstream index is built with **`mxbai-embed-large-v1`** (Mixedbread AI),
1024-dimensional, cosine distance, L2-normalized. All content ingested via
the `*_ingest_*` tools is embedded with this model. Pre-computed query
vectors must match this embedding space — mixing models silently returns
nonsense.

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
├── bridge/         # @vortex-enclave/mcp-server — stdio bridge (Node)
├── python/         # vortex-enclave — Python SDK (sync + async)
├── typescript/     # @vortex-enclave/sdk — TS/JS SDK
├── README.md       # you are here
└── LICENSE         # MIT, applies to everything in this repo
```

The Vortex Enclave platform itself (AWS CDK, Go Lambda proxy, Next.js portal,
Python ingestion worker) lives in a separate private monorepo. This
repository contains only the client-facing pieces.

## License

MIT — see [LICENSE](./LICENSE). Each package's `README.md` has its own
quickstart and full API reference.
