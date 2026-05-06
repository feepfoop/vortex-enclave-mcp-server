/**
 * Native TypeScript/JavaScript client for Vortex Enclave.
 *
 * Talks to the hosted /mcp endpoint over HTTPS, hides the JSON-RPC envelope,
 * returns typed results. Works in Node 20+ and any modern browser (uses
 * native fetch).
 */

const DEFAULT_ENDPOINT =
  "https://pbwwuvheu3rhomks6owwjolkjq0lhlht.lambda-url.us-east-1.on.aws/mcp";
const USER_AGENT = "vortex-enclave-ts/0.1.0";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type Role = "admin" | "editor" | "viewer";
export type KeyType = "api" | "mcp";
export type EventKind =
  | "ingest_text"
  | "ingest_url"
  | "forget"
  | "link"
  | "query"
  | string;

export interface Identity {
  org_id: string;
  user_id: string;
  role: Role;
  type: KeyType;
  scopes: string[];
}

export interface QueryResultItem {
  key: string;
  distance: number;
  hop: number;
  metadata: Record<string, unknown>;
}

export interface QueryResponse {
  results: QueryResultItem[];
  count: number;
  org_id: string;
}

export interface IngestResult {
  doc_id: string;
  status: "queued";
  estimated_seconds: number;
  source_uri: string;
}

export interface DocumentSummary {
  doc_id: string;
  chunk_count: number;
  ingested_at: number;
}

export interface DocumentListResponse {
  documents: DocumentSummary[];
  count: number;
  scanned: number;
  truncated: boolean;
}

export interface DocumentChunk {
  key: string;
  metadata: Record<string, unknown>;
}

export interface DocumentChunks {
  doc_id: string;
  chunks: DocumentChunk[];
  count: number;
}

export interface OrgStats {
  org_id: string;
  total_chunks: number;
  total_documents: number;
  oldest_ingest_ts: number;
  newest_ingest_ts: number;
  scanned: number;
  truncated: boolean;
  text_embedding: boolean;
}

export interface LogEvent {
  ts: number;
  kind: EventKind;
  user_id?: string;
  doc_id?: string;
  key_hash?: string;
  detail?: Record<string, unknown>;
}

export interface LogResponse {
  org_id: string;
  events: LogEvent[];
  count: number;
  since: number;
}

export interface LinkResult {
  from_key: string;
  to_key: string;
  status: "linked" | "already_linked";
  edges: string[];
}

export interface ForgetResult {
  doc_id: string;
  deleted_chunks: number;
  raw_object_dropped: boolean;
  raw_object_error?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Errors — typed by JSON-RPC error code
// ─────────────────────────────────────────────────────────────────────────────

export class VortexError extends Error {
  code?: number;
  data?: unknown;
  constructor(message: string, code?: number, data?: unknown) {
    super(message);
    this.name = "VortexError";
    this.code = code;
    this.data = data;
  }
}

export class VortexAuthError extends VortexError {
  constructor(message: string, data?: unknown) {
    super(message, -32001, data);
    this.name = "VortexAuthError";
  }
}

export class VortexScopeError extends VortexError {
  constructor(message: string, data?: unknown) {
    super(message, -32003, data);
    this.name = "VortexScopeError";
  }
}

export class VortexInvalidParamsError extends VortexError {
  constructor(message: string, data?: unknown) {
    super(message, -32602, data);
    this.name = "VortexInvalidParamsError";
  }
}

export class VortexInternalError extends VortexError {
  constructor(message: string, data?: unknown) {
    super(message, -32603, data);
    this.name = "VortexInternalError";
  }
}

function raiseForJsonRpcError(err: {
  code?: number;
  message?: string;
  data?: unknown;
}): never {
  const code = err.code;
  const msg = err.message ?? "unknown error";
  if (code === -32001) throw new VortexAuthError(msg, err.data);
  if (code === -32003) throw new VortexScopeError(msg, err.data);
  if (code === -32602) throw new VortexInvalidParamsError(msg, err.data);
  if (code === -32603) throw new VortexInternalError(msg, err.data);
  throw new VortexError(msg, code, err.data);
}

// ─────────────────────────────────────────────────────────────────────────────
// Client
// ─────────────────────────────────────────────────────────────────────────────

export interface VortexClientOptions {
  /** MCP key. Falls back to process.env.VORTEX_API_KEY. */
  apiKey?: string;
  /** Override the hosted /mcp endpoint (for self-hosted deployments). */
  endpoint?: string;
  /** Custom fetch implementation (for testing or proxies). */
  fetchImpl?: typeof fetch;
  /** Per-request timeout in milliseconds. Default 30s. */
  timeoutMs?: number;
}

export interface QueryOptions {
  topK?: number;
  expand?: boolean;
}

export interface IngestTextOptions {
  title?: string;
  docId?: string;
  tags?: Record<string, string>;
}

export interface IngestUrlOptions {
  docId?: string;
  tags?: Record<string, string>;
}

export interface LogOptions {
  since?: number;
  limit?: number;
  kind?: EventKind;
}

export class VortexClient {
  private readonly apiKey: string;
  private readonly endpoint: string;
  private readonly fetchImpl: typeof fetch;
  private readonly timeoutMs: number;

  constructor(options: VortexClientOptions = {}) {
    const apiKey =
      options.apiKey ??
      (typeof process !== "undefined"
        ? process.env?.VORTEX_API_KEY
        : undefined);
    if (!apiKey) {
      throw new Error(
        "apiKey is required (pass to constructor or set VORTEX_API_KEY env var)",
      );
    }
    this.apiKey = apiKey;
    this.endpoint =
      options.endpoint ??
      (typeof process !== "undefined"
        ? process.env?.VORTEX_MCP_ENDPOINT
        : undefined) ??
      DEFAULT_ENDPOINT;
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.timeoutMs = options.timeoutMs ?? 30_000;
  }

  // ── identity ───────────────────────────────────────────────────────────

  async whoami(): Promise<Identity> {
    return this.toolCall<Identity>("vortex_whoami", {});
  }

  // ── ingest ─────────────────────────────────────────────────────────────

  async ingestText(text: string, options: IngestTextOptions = {}): Promise<IngestResult> {
    const args: Record<string, unknown> = { text };
    if (options.title !== undefined) args.title = options.title;
    if (options.docId !== undefined) args.doc_id = options.docId;
    if (options.tags !== undefined) args.tags = options.tags;
    return this.toolCall<IngestResult>("vortex_ingest_text", args);
  }

  async ingestUrl(url: string, options: IngestUrlOptions = {}): Promise<IngestResult> {
    const args: Record<string, unknown> = { url };
    if (options.docId !== undefined) args.doc_id = options.docId;
    if (options.tags !== undefined) args.tags = options.tags;
    return this.toolCall<IngestResult>("vortex_ingest_url", args);
  }

  // ── browse ─────────────────────────────────────────────────────────────

  async listDocuments(limit = 50): Promise<DocumentListResponse> {
    return this.toolCall<DocumentListResponse>("vortex_list_documents", { limit });
  }

  async getDocument(docId: string): Promise<DocumentChunks> {
    return this.toolCall<DocumentChunks>("vortex_get_document", { doc_id: docId });
  }

  // ── recall ─────────────────────────────────────────────────────────────

  async query(
    textOrVector: string | number[],
    options: QueryOptions = {},
  ): Promise<QueryResponse> {
    const args: Record<string, unknown> = {
      top_k: options.topK ?? 10,
      expand: options.expand ?? true,
    };
    if (typeof textOrVector === "string") args.text = textOrVector;
    else args.vector = textOrVector;
    return this.toolCall<QueryResponse>("vortex_query", args);
  }

  // ── curation ───────────────────────────────────────────────────────────

  async link(
    fromKey: string,
    toKey: string,
    options: { kind?: string } = {},
  ): Promise<LinkResult> {
    const args: Record<string, unknown> = { from_key: fromKey, to_key: toKey };
    if (options.kind !== undefined) args.kind = options.kind;
    return this.toolCall<LinkResult>("vortex_link", args);
  }

  async log(options: LogOptions = {}): Promise<LogResponse> {
    const args: Record<string, unknown> = { limit: options.limit ?? 50 };
    if (options.since !== undefined) args.since = options.since;
    if (options.kind !== undefined) args.kind = options.kind;
    return this.toolCall<LogResponse>("vortex_log", args);
  }

  async forget(docId: string): Promise<ForgetResult> {
    return this.toolCall<ForgetResult>("vortex_forget", { doc_id: docId });
  }

  // ── reflect ────────────────────────────────────────────────────────────

  async stats(): Promise<OrgStats> {
    return this.toolCall<OrgStats>("vortex_stats", {});
  }

  // ─────────────────────────────────────────────────────────────────────────
  // JSON-RPC plumbing — hidden from users
  // ─────────────────────────────────────────────────────────────────────────

  private async toolCall<T>(name: string, args: Record<string, unknown>): Promise<T> {
    const payload = {
      jsonrpc: "2.0",
      id: crypto.randomUUID(),
      method: "tools/call",
      params: { name, arguments: args },
    };

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), this.timeoutMs);
    let response: Response;
    try {
      response = await this.fetchImpl(this.endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-MCP-Key": this.apiKey,
          "User-Agent": USER_AGENT,
        },
        body: JSON.stringify(payload),
        signal: ctrl.signal,
      });
    } finally {
      clearTimeout(timer);
    }
    if (response.status >= 500) {
      throw new VortexInternalError(`HTTP ${response.status} from /mcp`);
    }
    const body = (await response.json()) as {
      result?: {
        structuredContent?: T;
        content?: unknown;
      };
      error?: { code?: number; message?: string; data?: unknown };
    };
    if (body.error) raiseForJsonRpcError(body.error);
    if (!body.result) {
      throw new VortexInternalError("server returned no result");
    }
    if (body.result.structuredContent !== undefined) {
      return body.result.structuredContent;
    }
    return body.result as unknown as T;
  }
}
