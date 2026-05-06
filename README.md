# @vortex-enclave/mcp-server

[![license](https://img.shields.io/npm/l/@vortex-enclave/mcp-server.svg)](./LICENSE)

MCP stdio bridge for [Vortex Enclave](https://fusionlab.ai). Spawned by MCP
hosts (Claude Desktop, Cursor, Continue, custom stdio clients) — translates
stdio JSON-RPC to the hosted `/mcp` Streamable HTTP endpoint and back.

## What it does

```
   ┌────────────────┐    stdio JSON-RPC    ┌──────────────────────┐    HTTPS    ┌──────────────────────┐
   │ Claude Desktop │ ──────────────────▶  │ this bridge (Node)   │ ──────────▶ │ Vortex Enclave /mcp  │
   │ Cursor / etc.  │                      │ adds X-MCP-Key       │             │ (AWS Lambda)         │
   └────────────────┘    stdio JSON-RPC    └──────────────────────┘    HTTPS    └──────────────────────┘
                       ◀──────────────────                          ◀──────────
```

Eight tools are exposed by the upstream server: `vortex_whoami`, `vortex_query`,
`vortex_ingest_text`, `vortex_ingest_url`, `vortex_list_documents`,
`vortex_get_document`, `vortex_forget`, `vortex_stats`.

## Install — once published to npm

```jsonc
// claude_desktop_config.json
{
  "mcpServers": {
    "vortex-enclave": {
      "command": "npx",
      "args": ["-y", "@vortex-enclave/mcp-server"],
      "env": {
        "VORTEX_API_KEY": "mcp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

Mint a `VORTEX_API_KEY` in the portal at <https://fusionlab.ai> → MCP Keys.

## Install — from this repo (works today)

If you want to use it before the npm publish:

```bash
git clone https://github.com/feepfoop/vortex-enclave-mcp-server.git ~/vortex-enclave-mcp-server
```

Then point your MCP host config at the local file:

```jsonc
{
  "mcpServers": {
    "vortex-enclave": {
      "command": "node",
      "args": ["/Users/you/vortex-enclave-mcp-server/index.js"],
      "env": {
        "VORTEX_API_KEY": "mcp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

## Configuration paths per host

| Host | Config file |
|---|---|
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Claude Desktop (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` |
| Cursor (global) | `~/.cursor/mcp.json` |
| Cursor (project) | `<repo>/.cursor/mcp.json` |
| Continue 1.0+ | `~/.continue/config.yaml` (under `mcpServers:`) |
| Continue 0.x | `~/.continue/config.json` (under `experimental.modelContextProtocolServers`) |

Restart the host after saving the config.

## Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `VORTEX_API_KEY` | yes | — | MCP key from the portal. Format: `mcp_<32 hex>`. |
| `VORTEX_MCP_ENDPOINT` | no | hosted Vortex Enclave endpoint | Override for self-hosted deployments. |

## How auth works

The bridge sends `X-MCP-Key: $VORTEX_API_KEY` on every request to `/mcp`. The
upstream server SHA-256-hashes the key and looks up SSM at `/vortex/keys/{hash}`
to retrieve `{org_id, role, scopes}`. Each tool call is then RBAC-checked
against the role.

Agents inherit **the role of whoever minted the key**, downgraded if the human
chose a stricter scope when creating it. A `viewer`-scoped MCP key cannot call
ingest tools regardless of what the agent asks for.

## Development

```bash
git clone https://github.com/feepfoop/vortex-enclave-mcp-server.git
cd vortex-enclave-mcp-server
node index.js   # reads stdin, forwards to /mcp
```

Test by piping JSON-RPC into stdin (LSP framing OR newline-delimited):

```bash
VORTEX_API_KEY=mcp_xxx node index.js <<EOF
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
EOF
```

## Related

- The Vortex Enclave platform itself (private monorepo): the AWS infra, Go
  proxy, Next.js portal, and Python ingestion worker live there.
- Landing page: <https://fusionlab.ai>

## License

MIT — see [LICENSE](./LICENSE).
