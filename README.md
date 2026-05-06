# @vortex-enclave/mcp-server

Stdio MCP bridge for [Vortex Enclave](https://fusionlab.ai). Spawned by MCP
hosts (Claude Desktop, Cursor, Continue) — translates stdio JSON-RPC to the
hosted `/mcp` Streamable HTTP endpoint and back.

## Install

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

Mint your `VORTEX_API_KEY` in the portal at <https://fusionlab.ai> → MCP Keys.

## Local install (alternative to npm)

If you don't want to wait for the npm publish, point the host directly at the
file:

```jsonc
{
  "mcpServers": {
    "vortex-enclave": {
      "command": "node",
      "args": ["/absolute/path/to/vortex-enclave/mcp-bridge/index.js"],
      "env": {
        "VORTEX_API_KEY": "mcp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

## Optional environment variables

| Variable | Default | Purpose |
|---|---|---|
| `VORTEX_API_KEY` | — | **Required.** MCP key from the portal. |
| `VORTEX_MCP_ENDPOINT` | `https://...lambda-url.us-east-1.on.aws/mcp` | Override for self-hosted deployments. |

## What this server provides

The hosted `/mcp` endpoint exposes (today):

- `vortex_whoami` — returns identity + role + scopes for the auth'd key
- `vortex_query` — semantic search with knowledge-graph expansion

Roles (`admin`/`editor`/`viewer`) and the per-tool scope checks happen on the
server. The bridge passes them through.

## License

MIT
