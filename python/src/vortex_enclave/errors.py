"""Typed exceptions matching the server's JSON-RPC error codes.

Mapping (from proxy/mcp.go):
  -32700 → VortexError                (parse error)
  -32600 → VortexError                (invalid request)
  -32601 → VortexError                (method not found)
  -32602 → VortexInvalidParamsError   (invalid arguments)
  -32603 → VortexInternalError        (server-side failure)
  -32001 → VortexAuthError            (missing/invalid X-MCP-Key)
  -32003 → VortexScopeError           (insufficient scope for tool)
"""

from __future__ import annotations
from typing import Any


class VortexError(Exception):
    """Base class for all Vortex Enclave client errors."""

    def __init__(self, message: str, code: int | None = None, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


class VortexAuthError(VortexError):
    """Authentication failed — missing or invalid X-MCP-Key."""


class VortexScopeError(VortexError):
    """The MCP key doesn't have the scope required for the tool you called.

    Check `data` for `{tool, required_scope, granted_scopes, role}`.
    """


class VortexInvalidParamsError(VortexError):
    """Server rejected the call's arguments (missing/wrong type/out of range)."""


class VortexInternalError(VortexError):
    """Server-side failure. Check `data` for the underlying error message."""


class VortexEmbeddingError(VortexError):
    """The vector you're trying to send doesn't match the upstream index's
    embedding contract — wrong dimension, or local embedder produced a value
    of the wrong shape. Server-side checks may also raise this for vectors
    that pass dimension but are obviously not L2-normalized."""


def raise_for_jsonrpc_error(err: dict[str, Any]) -> None:
    """Translate a JSON-RPC error envelope into a typed exception."""
    code = err.get("code")
    msg = err.get("message", "unknown error")
    data = err.get("data")
    if code == -32001:
        raise VortexAuthError(msg, code, data)
    if code == -32003:
        raise VortexScopeError(msg, code, data)
    if code == -32602:
        raise VortexInvalidParamsError(msg, code, data)
    if code == -32603:
        raise VortexInternalError(msg, code, data)
    raise VortexError(msg, code, data)
