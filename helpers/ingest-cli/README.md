# vortex-ingest

Walk a directory or codebase and upload every relevant file into Vortex
Enclave so an agent can RAG it. Designed for one-shot bulk ingestion —
"I have a folder, get it queryable."

Lives in the public [vortex-enclave-mcp-server](https://github.com/feepfoop/vortex-enclave-mcp-server)
repo alongside the bridge, Python SDK, and TypeScript SDK.

## Install

```bash
# Minimal — text + code + Markdown only.
pip install "git+https://github.com/feepfoop/vortex-enclave-mcp-server.git#subdirectory=helpers/ingest-cli"

# Recommended — adds PDF / DOCX / PPTX / HTML / Notebook parsers.
pip install "git+https://github.com/feepfoop/vortex-enclave-mcp-server.git#subdirectory=helpers/ingest-cli[docs]"
```

Once published to PyPI:

```bash
pip install vortex-ingest-cli           # minimal
pip install 'vortex-ingest-cli[docs]'   # with rich-doc parsers
```

## Quick start

```bash
export VORTEX_API_KEY=mcp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Dry-run first — shows what would be uploaded, doesn't call the API
vortex-ingest ./my-repo --dry-run

# For real
vortex-ingest ./my-repo

# With tags so you can filter by them later in queries
vortex-ingest ./docs --tag project=portal --tag env=prod
```

## What it does

1. **Walks the directory tree** from your path.
   - Honors `.gitignore` and `.vortexignore` (gitignore syntax)
   - Never descends into common junk dirs: `node_modules`, `__pycache__`,
     `.venv`, `target`, `build`, `dist`, `.git`, etc.
   - Skips secrets by filename: `.env`, `id_rsa`, `credentials.json`, …
   - Skips files larger than `--max-size-mb` (default 5 MB)
2. **Classifies each file** by extension into one of:
   - `text` — code, config, plain text. Parsed as UTF-8.
   - `rich` — PDF / DOCX / PPTX / HTML / ipynb. Format-specific parser.
   - `tabular` — XLSX / CSV / TSV / Parquet. **Skipped by this CLI**;
     upload via the portal or `aws s3 cp` to trigger the worker's
     structured-data path (vortex_sql).
   - `binary` — images, archives, executables. Silently dropped.
   - `unknown` — anything else. Logged + dropped.
3. **Calls `vortex_ingest_text`** for each parsed file, with metadata:
   - `doc_id`: derived from the relative path
     (`src/utils/text.py` → `src_utils_text_py`)
   - `title`: the relative path itself
   - `tags`: `{source: "vortex-ingest-cli", parser: ..., rel_path: ...,
     ...your --tag values}`

Behind the scenes the proxy queues the upload; the worker chunks,
embeds, and writes vectors. Queries against the corpus work
immediately after the worker has drained the queue (~10s per doc).

## Flags

```
PATH                     directory or file to ingest

--api-key TEXT           MCP key (env: VORTEX_API_KEY)
--endpoint TEXT          override /mcp URL (env: VORTEX_MCP_ENDPOINT)
--prefix TEXT            prefix added to every doc_id
--tag key=value          repeatable; attached to every doc as metadata
--max-size-mb FLOAT      skip files > N MB (default 5.0)
--exclude PATTERN        repeatable; .gitignore syntax
--no-gitignore           do NOT honor .gitignore / .vortexignore
--dry-run                walk + classify, don't upload
--limit N                stop after N files (for testing)
-v, --verbose            verbose logging
```

## File-type coverage

| Category | Extensions | Parser |
|---|---|---|
| **Plain text** | `.txt .md .markdown .rst .log` | UTF-8 decode |
| **Code** | `.py .js .ts .tsx .jsx .go .rs .java .c .cpp .cs .rb .php .sh ...` (40+) | UTF-8 decode |
| **Config** | `.json .yaml .toml .ini .xml .tf ...` | UTF-8 decode |
| **PDF** | `.pdf` | `pypdf` (install `[docs]` extra) |
| **Word** | `.docx` | `python-docx`, preserves headings |
| **PowerPoint** | `.pptx` | `python-pptx`, one section per slide |
| **HTML** | `.html .htm` | `trafilatura` extracts main content |
| **Jupyter** | `.ipynb` | stdlib `json`, MD + code cells; outputs dropped |
| **Tabular** | `.csv .tsv .xlsx .xls .parquet` | skipped; upload via portal for `vortex_sql` |
| **Binary** | images, video, archives, executables | silently skipped |

## `.vortexignore`

Same syntax as `.gitignore`. Put it at the root of the path you're
ingesting. Useful when you want to ingest a directory that's not a git
repo, or to exclude things `.gitignore` allows (e.g. exclude generated
docs that are committed but you don't want in RAG).

```
# .vortexignore
generated/
*.min.js
fixtures/large-test-data/
```

## Doc-ID stability

The CLI derives `doc_id` deterministically from the relative path. This
means **re-running the CLI re-uploads under the same doc_ids** — Vortex
treats each upload as a new ingestion, so chunks accumulate over time
unless you delete the old ones first.

If you're doing iterative ingestion of an evolving codebase, the
recommended flow is:

```bash
# Get the list of stale doc_ids
vortex-ingest ./repo --dry-run --prefix old > stale.txt
# Forget them (via the Python SDK or vortex_forget MCP tool)
# Then re-ingest with the fresh prefix
vortex-ingest ./repo --prefix v2
```

A future flag `--replace` will do this automatically. Tracked in the
TODO.

## Authentication

The CLI uses the same MCP key system as everything else in Vortex. The
key inherits the role of whoever minted it; a `viewer` MCP key cannot
ingest. Mint an `ingest`-scoped key from the portal.

## Costs

A typical mid-size monorepo (~10k files, ~500 of them text/code, average
file ~5 KB) takes a few minutes to walk + upload and produces ~2,500
chunks in Vortex (post-chunking with the worker's 1000-char windows).

At hosted pricing: 2,500 chunks × 1024-d × 4 bytes ≈ 10 MB of stored
vectors = $0.0006/mo. The ingest itself triggers no extra API cost
beyond the `vortex_ingest_text` calls themselves.

## Why a separate package

Keeping it in `helpers/` rather than baking it into the main Python SDK
keeps the SDK lean (one runtime dep: `httpx`). The CLI takes optional
extras for the rich-doc parsers (`python-docx`, `python-pptx`, etc.)
which most users don't need.

## License

MIT — see [../../LICENSE](../../LICENSE).
