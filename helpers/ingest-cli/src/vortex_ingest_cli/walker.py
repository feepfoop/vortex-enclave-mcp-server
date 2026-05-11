"""Walk a directory, respect .gitignore and .vortexignore, yield files."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import pathspec

log = logging.getLogger(__name__)


# Sensible defaults — never ingest these regardless of .gitignore status.
ALWAYS_SKIP_DIRS = {
    ".git", ".hg", ".svn",
    "node_modules", "__pycache__", ".venv", "venv", "env",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox",
    "target", "build", "dist", "out", ".next", ".nuxt",
    ".cdk.staging", "cdk.out",
    ".idea", ".vscode",
    ".terraform",
    ".cache", ".npm", ".yarn", ".pnpm-store",
}

# Files we never want to upload, even if not in .gitignore.
ALWAYS_SKIP_FILES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "id_rsa", "id_ed25519", "credentials", "credentials.json",
    ".npmrc", ".pypirc",
}


@dataclass
class FileEntry:
    """A file selected for ingestion."""

    abs_path: Path
    """Absolute path on disk."""

    rel_path: Path
    """Path relative to the root (used to derive doc_id)."""

    size_bytes: int


def load_ignore_spec(root: Path) -> pathspec.PathSpec:
    """Combine .gitignore + .vortexignore (if present) into one PathSpec."""
    patterns: list[str] = []
    for fname in (".gitignore", ".vortexignore"):
        p = root / fname
        if p.is_file():
            patterns.extend(p.read_text(encoding="utf-8", errors="ignore").splitlines())
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def walk(
    root: Path,
    *,
    max_size_mb: float = 5.0,
    respect_ignore: bool = True,
    extra_excludes: Optional[list[str]] = None,
) -> Iterator[FileEntry]:
    """Yield every file under `root` that should be considered for ingestion.

    - Skips ALWAYS_SKIP_DIRS / ALWAYS_SKIP_FILES regardless of flags.
    - Respects .gitignore + .vortexignore if `respect_ignore=True` (default).
    - Skips files > max_size_mb to avoid blowing up on giant binaries.
    """
    root = root.resolve()
    spec = load_ignore_spec(root) if respect_ignore else pathspec.PathSpec([])
    extra = pathspec.PathSpec.from_lines("gitwildmatch", extra_excludes or [])
    max_bytes = int(max_size_mb * 1024 * 1024)

    for entry in root.rglob("*"):
        if not entry.is_file():
            continue

        # ALWAYS_SKIP_DIRS check — any parent dir in the skip set?
        parts = set(entry.relative_to(root).parts[:-1])
        if parts & ALWAYS_SKIP_DIRS:
            continue
        if entry.name in ALWAYS_SKIP_FILES:
            continue

        rel = entry.relative_to(root)
        rel_str = str(rel)
        if spec.match_file(rel_str) or extra.match_file(rel_str):
            continue

        try:
            size = entry.stat().st_size
        except OSError as e:
            log.warning("stat failed: %s (%s)", entry, e)
            continue
        if size == 0 or size > max_bytes:
            if size > max_bytes:
                log.debug("skip oversized: %s (%d MB)", entry, size // 1024 // 1024)
            continue

        yield FileEntry(abs_path=entry, rel_path=rel, size_bytes=size)
