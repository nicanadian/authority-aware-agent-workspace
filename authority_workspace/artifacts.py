"""Safe artifact writing helpers.

The helpers in this module only write beneath an explicit output root.  Artifact
paths are always caller-provided relative paths; absolute paths, parent
traversal, and symlink escapes are rejected before writing.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Iterable, Mapping, Sequence


class ArtifactError(ValueError):
    """Base class for artifact writer validation failures."""


class ArtifactPathError(ArtifactError):
    """Raised when an artifact path is not a safe path below the output root."""


class DuplicateArtifactError(ArtifactError):
    """Raised when a manifest would contain duplicate artifact paths."""


def _relative_path_string(relative_path: str | os.PathLike[str]) -> str:
    path_text = os.fspath(relative_path)
    if not path_text:
        raise ArtifactPathError("artifact path must not be empty")

    path = Path(path_text)
    if path.is_absolute():
        raise ArtifactPathError(f"absolute artifact paths are not allowed: {path_text!r}")
    if any(part == ".." for part in path.parts):
        raise ArtifactPathError(f"parent traversal is not allowed in artifact paths: {path_text!r}")
    if "\\" in path_text or any(ord(character) < 32 for character in path_text):
        raise ArtifactPathError(f"artifact paths must be POSIX-relative text paths: {path_text!r}")
    if path == Path("."):
        raise ArtifactPathError("artifact path must name a file")

    return path.as_posix()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_output_path(root: str | os.PathLike[str], relative_path: str | os.PathLike[str]) -> Path:
    """Resolve an artifact path safely below *root*.

    Only relative artifact paths are accepted.  Existing symlinked parents are
    resolved and the final path must remain below the resolved output root.
    The artifact root is expected to be a private run directory controlled by
    this process.  Existing symlink escapes are rejected, but callers should not
    share the root with untrusted concurrent writers.
    """

    relative_posix = _relative_path_string(relative_path)
    root_path = Path(root)
    root_resolved = root_path.resolve(strict=False)
    candidate = root_resolved / Path(relative_posix)
    candidate_resolved = candidate.resolve(strict=False)

    if not _is_relative_to(candidate_resolved, root_resolved):
        raise ArtifactPathError(
            f"artifact path escapes output root: {relative_posix!r}"
        )

    return candidate_resolved


def _prepare_parent(root: str | os.PathLike[str], relative_path: str | os.PathLike[str]) -> Path:
    path = resolve_output_path(root, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Re-check after mkdir in case an existing parent component is a symlink or
    # a race changed the path between validation and directory creation.
    path = resolve_output_path(root, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _json_dumps(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def write_jsonl(
    root: str | os.PathLike[str],
    relative_path: str | os.PathLike[str],
    records: Iterable[Mapping[str, object]],
) -> Path:
    """Write UTF-8 JSON Lines records below *root* and return the output path."""

    output_path = _prepare_parent(root, relative_path)
    text = "".join(f"{_json_dumps(record)}\n" for record in records)
    _replace_text_file(output_path, text)
    return output_path


def _replace_text_file(output_path: Path, text: str) -> None:
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, output_path)
        temp_name = None
    finally:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def write_json(
    root: str | os.PathLike[str],
    relative_path: str | os.PathLike[str],
    data: object,
) -> Path:
    """Atomically-ish write deterministic UTF-8 JSON below *root*."""

    output_path = _prepare_parent(root, relative_path)
    _replace_text_file(output_path, _json_dumps(data) + "\n")
    return output_path


def write_markdown(
    root: str | os.PathLike[str],
    relative_path: str | os.PathLike[str],
    text: str,
) -> Path:
    """Atomically-ish write UTF-8 Markdown text below *root*."""

    if not isinstance(text, str):
        raise TypeError("markdown text must be a string")
    output_path = _prepare_parent(root, relative_path)
    _replace_text_file(output_path, text)
    return output_path


def _jsonl_line_count(relative_posix: str, contents: bytes) -> int:
    if not relative_posix.endswith(".jsonl"):
        return 0
    if not contents:
        return 0
    return len(contents.decode("utf-8").splitlines())


def build_manifest_entries(
    root: str | os.PathLike[str],
    paths: Sequence[str | os.PathLike[str]],
) -> list[dict[str, object]]:
    """Build run-manifest artifact entries for *paths* below *root*.

    Each entry has the shape required by ``run-manifest.schema.json``:
    ``path``, ``sha256``, ``bytes``, and ``jsonl_line_count``.  Duplicate
    manifest paths are rejected before reading files.
    """

    entries: list[dict[str, object]] = []
    seen: set[str] = set()

    for artifact_path in paths:
        relative_posix = _relative_path_string(artifact_path)
        if relative_posix in seen:
            raise DuplicateArtifactError(f"duplicate artifact path: {relative_posix!r}")
        seen.add(relative_posix)

        output_path = resolve_output_path(root, relative_posix)
        contents = output_path.read_bytes()
        entries.append(
            {
                "path": relative_posix,
                "sha256": "sha256:" + hashlib.sha256(contents).hexdigest(),
                "bytes": len(contents),
                "jsonl_line_count": _jsonl_line_count(relative_posix, contents),
            }
        )

    return entries


__all__ = [
    "ArtifactError",
    "ArtifactPathError",
    "DuplicateArtifactError",
    "build_manifest_entries",
    "resolve_output_path",
    "write_json",
    "write_jsonl",
    "write_markdown",
]
