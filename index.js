#!/usr/bin/env node
/**
 * Vortex Enclave MCP stdio bridge.
 *
 * Designed to be spawned by an MCP host (Claude Desktop, Cursor, Continue).
 * Reads JSON-RPC messages from stdin, forwards them to the hosted /mcp
 * Streamable HTTP endpoint with X-MCP-Key auth, writes responses to stdout.
 *
 * Required env:
 *   VORTEX_API_KEY        — the mcp_... key minted from the portal
 * Optional env:
 *   VORTEX_MCP_ENDPOINT   — override the default Vortex Enclave endpoint
 *
 * Wire format (LSP/MCP-style framing):
 *   Each message is: Content-Length: <n>\r\n\r\n<json-payload>
 */

import process from "node:process";

const ENDPOINT =
  process.env.VORTEX_MCP_ENDPOINT ??
  "https://pbwwuvheu3rhomks6owwjolkjq0lhlht.lambda-url.us-east-1.on.aws/mcp";

const API_KEY = process.env.VORTEX_API_KEY;

if (!API_KEY) {
  process.stderr.write(
    "[vortex-enclave/mcp-server] VORTEX_API_KEY env var is required.\n" +
      "Mint one in the portal at https://fusionlab.ai → MCP Keys.\n",
  );
  process.exit(1);
}

// ── Forward a single JSON-RPC request to the hosted /mcp endpoint ─────────────

async function forward(payload) {
  let body;
  try {
    const res = await fetch(ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-MCP-Key": API_KEY,
        "User-Agent": "vortex-enclave-mcp-server/0.1.0",
      },
      body: payload,
    });
    body = await res.text();
    if (!res.ok && !body) {
      // Construct a JSON-RPC error if the server didn't give us one
      const id = safeId(payload);
      body = JSON.stringify({
        jsonrpc: "2.0",
        id,
        error: {
          code: -32603,
          message: `bridge: HTTP ${res.status} from /mcp`,
        },
      });
    }
  } catch (err) {
    const id = safeId(payload);
    body = JSON.stringify({
      jsonrpc: "2.0",
      id,
      error: {
        code: -32603,
        message: `bridge: network error: ${err.message ?? err}`,
      },
    });
  }
  return body;
}

function safeId(rawJson) {
  try {
    return JSON.parse(rawJson).id ?? null;
  } catch {
    return null;
  }
}

// ── stdio framing — Content-Length: <n>\r\n\r\n<json> ─────────────────────────

function writeFramed(jsonString) {
  if (!jsonString || !jsonString.trim()) return;
  const buf = Buffer.from(jsonString, "utf8");
  process.stdout.write(`Content-Length: ${buf.length}\r\n\r\n`);
  process.stdout.write(buf);
}

let buffer = Buffer.alloc(0);
let pending = 0;
let stdinClosed = false;

function maybeExit() {
  if (stdinClosed && pending === 0) process.exit(0);
}

async function handle(payload) {
  pending += 1;
  try {
    const reply = await forward(payload);
    if (reply && reply.trim()) writeFramed(reply);
  } finally {
    pending -= 1;
    maybeExit();
  }
}

process.stdin.on("data", (chunk) => {
  buffer = Buffer.concat([buffer, chunk]);

  // Parse as many complete LSP-framed messages as we have
  while (true) {
    const headerEnd = buffer.indexOf("\r\n\r\n");
    if (headerEnd === -1) {
      // Some hosts (and a lot of test code) send raw newline-delimited JSON
      // instead of LSP framing. Try that as a fallback.
      const lineEnd = buffer.indexOf("\n");
      if (lineEnd === -1) return;
      const line = buffer.slice(0, lineEnd).toString("utf8").trim();
      buffer = buffer.slice(lineEnd + 1);
      if (line) handle(line);
      continue;
    }

    const header = buffer.slice(0, headerEnd).toString("utf8");
    const match = /Content-Length:\s*(\d+)/i.exec(header);
    if (!match) {
      buffer = buffer.slice(headerEnd + 4);
      continue;
    }
    const len = parseInt(match[1], 10);
    if (buffer.length < headerEnd + 4 + len) return;

    const payload = buffer.slice(headerEnd + 4, headerEnd + 4 + len).toString("utf8");
    buffer = buffer.slice(headerEnd + 4 + len);
    handle(payload);
  }
});

process.stdin.on("end", () => {
  stdinClosed = true;
  maybeExit();
});
process.on("SIGINT", () => process.exit(0));
process.on("SIGTERM", () => process.exit(0));
