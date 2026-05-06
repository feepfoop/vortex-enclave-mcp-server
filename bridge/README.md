# @vortex-enclave/mcp-server (stdio bridge)

[![license](https://img.shields.io/npm/l/@vortex-enclave/mcp-server.svg)](../LICENSE)

MCP stdio bridge for [Vortex Enclave](https://fusionlab.ai). Spawned by MCP
hosts (Claude Desktop, Cursor, Continue, custom stdio clients) — translates
stdio JSON-RPC to the hosted `/mcp` Streamable HTTP endpoint and back.

> **If you're writing your own code in Python or TypeScript**, you probably
> want a [native SDK](../README.md) instead. This bridge is specifically for
> MCP-host integrations that spawn an external process over stdio.

## What it does

```
   ┌────────────────┐    stdio JSON-RPC    ┌──────────────────────┐    HTTPS    ┌──────────────────────┐
   │ Claude Desktop │ ──────────────────▶  │ this bridge (Node)   │ ──────────▶ │ Vortex Enclave /mcp  │
   │ Cursor / etc.  │                      │ adds X-MCP-Key       │             │ (AWS Lambda)         │
   └────────────────┘    stdio JSON-RPC    └──────────────────────┘    HTTPS    └──────────────────────┘
                       ◀──────────────────                          ◀──────────
```

Ten tools are exposed by the upstream server. See the [repo root README](../README.md)
for the full table.

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

## Install — from this repo (works today)

```bash
git clone https://github.com/feepfoop/vortex-enclave-mcp-server.git ~/vortex-enclave-mcp-server
```

Then point your MCP host config at the local file:

```jsonc
{
  "mcpServers": {
    "vortex-enclave": {
      "command": "node",
      "args": ["/Users/you/vortex-enclave-mcp-server/bridge/index.js"],
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

## Development

```bash
cd vortex-enclave-mcp-server/bridge
node index.js   # reads stdin, forwards to /mcp
```

Test by piping JSON-RPC into stdin (LSP framing OR newline-delimited):

```bash
VORTEX_API_KEY=mcp_xxx node index.js <<EOF
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
EOF
```

## License

MIT — see [../LICENSE](../LICENSE).
