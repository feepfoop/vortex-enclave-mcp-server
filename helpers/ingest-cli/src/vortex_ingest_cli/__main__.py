"""CLI entry point for vortex-ingest.

Usage:
  vortex-ingest <path> [options]

Walks a directory (or file), parses each file according to its type, and
uploads to Vortex via vortex_ingest_text. Tabular files (xlsx/csv) are
deferred — they'd need raw-bucket upload which requires AWS creds; this
v1 of the CLI only uses the MCP API and skips them with a clear note.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn, TimeElapsedColumn
from rich.table import Table

from vortex_enclave import VortexClient, VortexError

from .parsers import classify, parser_for, ParsedFile
from .walker import walk, FileEntry

console = Console()
log = logging.getLogger("vortex-ingest")

# Stable, SQL-safe identifier from a file path.
_safe = re.compile(r"[^a-zA-Z0-9_]+")


def derive_doc_id(rel_path: Path, prefix: str | None = None) -> str:
    """Convert 'src/utils/text.py' → 'src_utils_text_py' (+ optional prefix)."""
    base = _safe.sub("_", str(rel_path)).strip("_").lower()
    if prefix:
        return f"{prefix}_{base}"[:128]
    return base[:128]


def show_classify_summary(entries: list[FileEntry]) -> None:
    """Group selected files by classification (text / rich / tabular / unknown)."""
    buckets: dict[str, list[FileEntry]] = {}
    for e in entries:
        buckets.setdefault(classify(e.abs_path), []).append(e)
    table = Table(title="Files to ingest", show_lines=False)
    table.add_column("Type", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Total bytes", justify="right")
    for kind in ("text", "rich", "tabular", "binary", "unknown"):
        bucket = buckets.get(kind, [])
        table.add_row(
            kind,
            str(len(bucket)),
            f"{sum(e.size_bytes for e in bucket):,}",
        )
    console.print(table)


@click.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--api-key", envvar="VORTEX_API_KEY",
              help="MCP key. Falls back to $VORTEX_API_KEY.")
@click.option("--endpoint", envvar="VORTEX_MCP_ENDPOINT",
              help="Override the hosted /mcp endpoint.")
@click.option("--prefix", default=None,
              help="Prefix added to every doc_id (useful for tagging a corpus).")
@click.option("--tag", "tags", multiple=True,
              help="Extra tag: --tag key=value (repeatable). Attached to every doc.")
@click.option("--max-size-mb", default=5.0, type=float,
              help="Skip files larger than this many MB (default 5).")
@click.option("--exclude", "extra_excludes", multiple=True,
              help="Extra glob to exclude (repeatable, .gitignore syntax).")
@click.option("--no-gitignore", is_flag=True,
              help="Don't honor .gitignore / .vortexignore.")
@click.option("--dry-run", is_flag=True,
              help="Walk + parse but don't upload. Prints what would happen.")
@click.option("--limit", type=int, default=None,
              help="Stop after N files (for testing).")
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging.")
def cli(
    path: Path,
    api_key: str | None,
    endpoint: str | None,
    prefix: str | None,
    tags: tuple[str, ...],
    max_size_mb: float,
    extra_excludes: tuple[str, ...],
    no_gitignore: bool,
    dry_run: bool,
    limit: int | None,
    verbose: bool,
) -> None:
    """Walk PATH and upload every file Vortex can RAG.

    Examples:

        vortex-ingest ./my-repo --dry-run
        vortex-ingest ./docs --tag project=portal --tag env=prod
        vortex-ingest ./big-folder --exclude '*.test.*' --max-size-mb 2
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
    )

    if not dry_run and not api_key:
        console.print("[red]error:[/] --api-key or $VORTEX_API_KEY required "
                      "(use --dry-run to test without uploading)")
        sys.exit(2)

    tag_dict = _parse_tags(tags)

    # 1. Walk
    if path.is_file():
        entries = [FileEntry(abs_path=path.resolve(),
                             rel_path=Path(path.name),
                             size_bytes=path.stat().st_size)]
    else:
        entries = list(walk(
            path,
            max_size_mb=max_size_mb,
            respect_ignore=not no_gitignore,
            extra_excludes=list(extra_excludes),
        ))
        if limit:
            entries = entries[:limit]

    if not entries:
        console.print("[yellow]no files found[/]")
        sys.exit(0)

    show_classify_summary(entries)

    if dry_run:
        console.print(f"\n[dim]dry-run — would upload {len(entries)} files[/]")
        sys.exit(0)

    # 2. Upload
    client = VortexClient(api_key=api_key, endpoint=endpoint) if not dry_run else None
    stats = {"text": 0, "rich": 0, "tabular": 0, "binary": 0, "unknown": 0,
             "skipped": 0, "failed": 0, "total_chars": 0}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("ingesting", total=len(entries))
        for entry in entries:
            kind = classify(entry.abs_path)
            try:
                progress.update(task, description=str(entry.rel_path)[:60])
                if kind == "binary":
                    stats["binary"] += 1
                    progress.advance(task)
                    continue
                if kind == "tabular":
                    # v1 of this CLI uses only MCP — raw-bucket upload would
                    # need AWS creds. Surface clearly and skip.
                    stats["tabular"] += 1
                    log.info("skipped tabular (use the portal or aws s3 cp): %s",
                             entry.rel_path)
                    progress.advance(task)
                    continue
                if kind == "unknown":
                    stats["unknown"] += 1
                    log.info("skipped (unknown ext): %s", entry.rel_path)
                    progress.advance(task)
                    continue

                parser = parser_for(entry.abs_path)
                if parser is None:
                    stats["unknown"] += 1
                    progress.advance(task)
                    continue

                raw = entry.abs_path.read_bytes()
                parsed: ParsedFile = parser(raw, entry.abs_path)
                if parsed.skipped_reason:
                    stats["skipped"] += 1
                    log.info("skipped %s: %s", entry.rel_path, parsed.skipped_reason)
                    progress.advance(task)
                    continue
                if not parsed.text.strip():
                    stats["skipped"] += 1
                    progress.advance(task)
                    continue

                doc_id = derive_doc_id(entry.rel_path, prefix)
                upload_tags = {
                    **tag_dict,
                    "source": "vortex-ingest-cli",
                    "parser": parsed.parser_name,
                    "rel_path": str(entry.rel_path),
                }
                assert client is not None
                client.ingest_text(
                    parsed.text,
                    title=str(entry.rel_path),
                    doc_id=doc_id,
                    tags=upload_tags,
                )
                stats[kind] += 1
                stats["total_chars"] += len(parsed.text)
            except VortexError as e:
                stats["failed"] += 1
                log.error("upload failed for %s: %s", entry.rel_path, e)
                time.sleep(0.5)  # mild backoff before continuing
            except Exception:
                stats["failed"] += 1
                log.exception("unexpected error for %s", entry.rel_path)
            finally:
                progress.advance(task)

    # 3. Summary
    summary = Table(title="Results", show_lines=False)
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", justify="right")
    summary.add_row("uploaded (text/code)", str(stats["text"]))
    summary.add_row("uploaded (rich docs)", str(stats["rich"]))
    summary.add_row("skipped (tabular — needs portal upload)", str(stats["tabular"]))
    summary.add_row("skipped (binary)", str(stats["binary"]))
    summary.add_row("skipped (unknown ext)", str(stats["unknown"]))
    summary.add_row("skipped (parse/empty)", str(stats["skipped"]))
    summary.add_row("failed", str(stats["failed"]))
    summary.add_row("total chars uploaded", f"{stats['total_chars']:,}")
    console.print(summary)

    if stats["failed"]:
        sys.exit(1)


def _parse_tags(tags: tuple[str, ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    for t in tags:
        if "=" not in t:
            console.print(f"[yellow]warn:[/] ignoring malformed tag '{t}' "
                          f"(expected key=value)")
            continue
        k, v = t.split("=", 1)
        out[k.strip()] = v.strip()
    return out


if __name__ == "__main__":
    cli()
