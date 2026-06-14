"""Bounded live-model smoke plumbing.

The live-smoke path intentionally performs one provider command invocation against one
materialized context record, records the result as non-authoritative evidence, and
then re-runs the deterministic evaluator. Provider integration is explicit and
bounded; no credentials or environment-specific provider assumptions live here.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Sequence

from authority_workspace.artifacts import build_manifest_entries, write_json, write_jsonl
from authority_workspace.evaluator import evaluate_run
from authority_workspace.report import generate_report
from authority_workspace.runner import RUN_ARTIFACT_PATHS, run_scenario


LIVE_SMOKE_OUTPUT_PATHS = (
    "live_smoke_trace.json",
    "live_model_outputs.jsonl",
)
MAX_TIMEOUT_SECONDS = 30


def run_live_smoke(
    scenario_path: str | Path,
    output_root: str | Path,
    *,
    provider_command: Sequence[str],
    timeout_seconds: int = 10,
    max_context_bytes: int = 8192,
    run_id: str = "deterministic-live-smoke",
) -> dict[str, Any]:
    """Run a one-call bounded live smoke against the first materialized context.

    ``provider_command`` is executed without a shell. It receives a JSON request on
    stdin and must write a JSON object or text on stdout. Regardless of provider
    wording, its output is stored as non-authoritative evidence and cannot grant
    authority.
    """

    command = _validate_provider_command(provider_command)
    _validate_bounds(timeout_seconds, max_context_bytes)
    root = Path(output_root)
    _remove_live_smoke_outputs(root)

    run_scenario(scenario_path, root, run_id=run_id)
    context_record = _first_materialized_context(root)
    context_text = str(context_record["context_text"])
    context_bytes = len(context_text.encode("utf-8"))
    if context_bytes > max_context_bytes:
        raise ValueError(f"materialized context exceeds max_context_bytes: {context_bytes} > {max_context_bytes}")

    request = _request_payload(context_record, context_bytes, max_context_bytes, timeout_seconds)
    completed = _call_provider(command, request, timeout_seconds)
    if completed.returncode != 0:
        _write_trace(root, request, completed, bounded=True)
        raise RuntimeError(f"provider command failed with exit code {completed.returncode}")

    output_record = _live_output_record(request, completed.stdout)
    write_jsonl(root, "live_model_outputs.jsonl", [output_record])
    _write_trace(root, request, completed, bounded=True)

    evaluate_run(root)
    generate_report(root)
    manifest = _read_manifest(root)
    manifest["artifacts"] = build_manifest_entries(root, (*RUN_ARTIFACT_PATHS, *LIVE_SMOKE_OUTPUT_PATHS))
    write_json(root, "run_manifest.json", manifest)
    return manifest


def _validate_provider_command(provider_command: Sequence[str]) -> list[str]:
    if isinstance(provider_command, (str, bytes)) or not provider_command:
        raise ValueError("provider_command must be a non-empty sequence of executable arguments")
    command = [str(part) for part in provider_command]
    if any(not part for part in command):
        raise ValueError("provider_command arguments must be non-empty strings")
    return command


def _remove_live_smoke_outputs(root: Path) -> None:
    for relative_path in LIVE_SMOKE_OUTPUT_PATHS:
        path = root / relative_path
        if path.exists():
            path.unlink()


def _validate_bounds(timeout_seconds: int, max_context_bytes: int) -> None:
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool) or timeout_seconds < 1 or timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout_seconds must be an integer from 1 to {MAX_TIMEOUT_SECONDS}")
    if not isinstance(max_context_bytes, int) or isinstance(max_context_bytes, bool) or max_context_bytes < 256:
        raise ValueError("max_context_bytes must be an integer >= 256")


def _first_materialized_context(root: Path) -> dict[str, Any]:
    path = root / "materialized_contexts.jsonl"
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("materialized context record must be a JSON object")
                return record
    raise ValueError("materialized_contexts.jsonl has no records")


def _request_payload(context_record: dict[str, Any], context_bytes: int, max_context_bytes: int, timeout_seconds: int) -> dict[str, Any]:
    return {
        "schema_version": "aaaw.live_smoke_request.v1",
        "call_index": 0,
        "bounded": True,
        "max_call_count": 1,
        "timeout_seconds": timeout_seconds,
        "max_context_bytes": max_context_bytes,
        "context_record_id": context_record["context_record_id"],
        "exposure_id": context_record["exposure_id"],
        "context_mode": context_record["context_mode"],
        "protocol": context_record["protocol"],
        "source_event_ids": context_record["source_event_ids"],
        "context_text": context_record["context_text"],
        "context_bytes": context_bytes,
        "context_sha256": _sha256_text(str(context_record["context_text"])),
        "instruction": (
            "Respond with a concise JSON object. Do not claim authority; any output is non-authoritative smoke evidence."
        ),
    }


def _call_provider(command: list[str], request: dict[str, Any], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            input=json.dumps(request, sort_keys=True),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        completed = subprocess.CompletedProcess(command, 124, stdout=exc.stdout or "", stderr=exc.stderr or "timeout")
        return completed


def _live_output_record(request: dict[str, Any], stdout: str) -> dict[str, Any]:
    parsed: Any
    try:
        parsed = json.loads(stdout) if stdout.strip() else {}
    except json.JSONDecodeError:
        parsed = {"text": stdout.strip()}
    return {
        "live_output_id": "live-output:0",
        "provider_call_index": 0,
        "source_context_record_id": request["context_record_id"],
        "source_context_sha256": request["context_sha256"],
        "source_event_ids": list(request["source_event_ids"]),
        "provider_output": parsed,
        "raw_stdout_sha256": _sha256_text(stdout),
        "grants_authority": False,
        "authority_effect": "none",
        "candidate_state_not_authority": True,
    }


def _write_trace(root: Path, request: dict[str, Any], completed: subprocess.CompletedProcess[str], *, bounded: bool) -> None:
    trace = {
        "schema_version": "aaaw.live_smoke_trace.v1",
        "bounded": bounded,
        "call_count": 1,
        "max_call_count": 1,
        "timeout_seconds": request["timeout_seconds"],
        "max_context_bytes": request["max_context_bytes"],
        "prompt_bytes": len(json.dumps(request, sort_keys=True).encode("utf-8")),
        "context_bytes": request["context_bytes"],
        "context_sha256": request["context_sha256"],
        "context_record_id": request["context_record_id"],
        "provider_exit_code": completed.returncode,
        "provider_stdout_bytes": len(str(completed.stdout).encode("utf-8")),
        "provider_stderr_bytes": len(str(completed.stderr).encode("utf-8")),
        "provider_stdout_sha256": _sha256_text(str(completed.stdout)),
        "provider_stderr_sha256": _sha256_text(str(completed.stderr)),
        "authority_effect": "none",
        "grants_authority": False,
        "candidate_state_not_authority": True,
    }
    write_json(root, "live_smoke_trace.json", trace)


def _read_manifest(root: Path) -> dict[str, Any]:
    manifest = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("run_manifest.json must be a JSON object")
    return manifest


def _sha256_text(text: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = ["LIVE_SMOKE_OUTPUT_PATHS", "run_live_smoke"]
