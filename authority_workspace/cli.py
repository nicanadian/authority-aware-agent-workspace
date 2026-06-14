"""Deterministic local command-line interface for authority workspace runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

from authority_workspace.artifacts import build_manifest_entries, write_json
from authority_workspace.evaluator import EVALUATOR_OUTPUT_PATHS, evaluate_run
from authority_workspace.report import REPORT_OUTPUT_PATHS, generate_report
from authority_workspace.runner import CANDIDATE_ARTIFACT_PATHS, INITIAL_ARTIFACT_PATHS, RUN_ARTIFACT_PATHS, RUNNER_VERSION, run_scenario
from authority_workspace.scenario import CONTEXT_MODES, FIXTURE_TYPES, PROTOCOLS, load_scenario


def main(argv: Sequence[str] | None = None) -> int:
    """Run the authority workspace CLI and return a process exit code."""

    parser = _parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
        if args.command == "run":
            return _run_command(args.scenario, args.out)
        if args.command == "evaluate":
            return _evaluate_command(args.run_root)
        parser.print_usage(sys.stderr)
        return 2
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
        return code if code != 0 else 0
    except Exception as exc:  # noqa: BLE001 - CLI boundary converts failures to nonzero exits.
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m authority_workspace.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run a scenario fixture into an output directory")
    run_parser.add_argument("scenario", type=Path)
    run_parser.add_argument("--out", required=True, type=Path)

    evaluate_parser = subparsers.add_parser("evaluate", help="re-evaluate an existing run directory")
    evaluate_parser.add_argument("run_root", type=Path)
    return parser


def _run_command(scenario: Path, output_root: Path) -> int:
    if not scenario.is_file():
        print(f"error: scenario not found: {scenario}", file=sys.stderr)
        return 1
    manifest = run_scenario(scenario, output_root)
    print(f"wrote run: {output_root}")
    print(f"scenario_id: {manifest['scenario_id']}")
    return 0


def _evaluate_command(run_root: Path) -> int:
    if not run_root.is_dir():
        print(f"error: run directory not found: {run_root}", file=sys.stderr)
        return 1
    _remove_derived_outputs(run_root)
    manifest = _read_manifest(run_root)
    _validate_public_evaluate_manifest(manifest)
    _validate_run_artifacts_match_trusted_fixture(run_root, manifest)
    _rewrite_manifest(run_root, (*INITIAL_ARTIFACT_PATHS, *CANDIDATE_ARTIFACT_PATHS))
    evaluate_run(run_root)
    generate_report(run_root)
    manifest = _rewrite_manifest(run_root, RUN_ARTIFACT_PATHS)
    print(f"evaluated run: {run_root}")
    print(f"scenario_id: {manifest['scenario_id']}")
    return 0


def _rewrite_manifest(run_root: Path, artifact_paths: Sequence[str]) -> dict[str, object]:
    manifest = _read_manifest(run_root)
    _validate_public_evaluate_manifest(manifest)
    manifest["artifacts"] = build_manifest_entries(run_root, artifact_paths)
    write_json(run_root, "run_manifest.json", manifest)
    return manifest


_MANIFEST_KEYS = {
    "schema_version",
    "run_id",
    "scenario_id",
    "scenario_sha256",
    "fixture_type",
    "protocol",
    "context_mode",
    "seed",
    "runner_version",
    "artifact_schema_version",
    "artifacts",
}
_ARTIFACT_ENTRY_KEYS = {"path", "sha256", "bytes", "jsonl_line_count"}
_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "scenarios" / "fixtures"


def _read_manifest(run_root: Path) -> dict[str, object]:
    manifest = json.loads((run_root / "run_manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("run_manifest.json must be a JSON object")
    return manifest


def _validate_public_evaluate_manifest(manifest: dict[str, object]) -> None:
    keys = set(manifest)
    missing = _MANIFEST_KEYS - keys
    if missing:
        raise ValueError(f"run_manifest.json missing required field(s): {', '.join(sorted(missing))}")
    unknown = keys - _MANIFEST_KEYS
    if unknown:
        raise ValueError(f"run_manifest.json has unknown field(s): {', '.join(sorted(unknown))}")
    if manifest["schema_version"] != "aaaw.run_manifest.v1":
        raise ValueError("run_manifest.json schema_version is not aaaw.run_manifest.v1")
    if manifest["artifact_schema_version"] != "aaaw.artifacts.v1":
        raise ValueError("run_manifest.json artifact_schema_version is not aaaw.artifacts.v1")
    _validate_non_empty_string(manifest["run_id"], "run_id")
    _validate_non_empty_string(manifest["scenario_id"], "scenario_id")
    _validate_sha256(manifest["scenario_sha256"], "scenario_sha256")
    _validate_fixture_type(manifest["fixture_type"])
    _validate_protocol(manifest["protocol"])
    _validate_context_mode(manifest["context_mode"])
    _validate_seed(manifest["seed"])
    if manifest["runner_version"] != RUNNER_VERSION:
        raise ValueError("run_manifest.json runner_version does not match this evaluator")
    if not isinstance(manifest["artifacts"], list):
        raise ValueError("run_manifest.json artifacts must be an array")
    for index, entry in enumerate(manifest["artifacts"]):
        _validate_artifact_entry(index, entry)
    _validate_trusted_fixture_provenance(manifest)


def _validate_artifact_entry(index: int, entry: Any) -> None:
    if not isinstance(entry, dict):
        raise ValueError(f"run_manifest.json artifacts[{index}] must be an object")
    entry_keys = set(entry)
    if entry_keys != _ARTIFACT_ENTRY_KEYS:
        raise ValueError(f"run_manifest.json artifacts[{index}] has invalid field set")
    _validate_non_empty_string(entry["path"], f"artifacts[{index}].path")
    _validate_sha256(entry["sha256"], f"artifacts[{index}].sha256")
    _validate_non_negative_integer(entry["bytes"], f"artifacts[{index}].bytes")
    _validate_non_negative_integer(entry["jsonl_line_count"], f"artifacts[{index}].jsonl_line_count")


def _validate_non_empty_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"run_manifest.json {field_name} must be a non-empty string")


def _validate_non_negative_integer(value: Any, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"run_manifest.json {field_name} must be a non-negative integer")


def _validate_sha256(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        raise ValueError(f"run_manifest.json {field_name} must be a sha256 digest")
    digest = value.removeprefix("sha256:")
    if any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(f"run_manifest.json {field_name} must be a lowercase sha256 digest")


def _validate_fixture_type(value: Any) -> None:
    if not isinstance(value, str) or value not in FIXTURE_TYPES:
        raise ValueError(f"run_manifest.json fixture_type is not a supported v0 fixture: {value}")


def _validate_protocol(value: Any) -> None:
    if not isinstance(value, str) or value not in PROTOCOLS:
        raise ValueError(f"run_manifest.json protocol is not supported: {value}")


def _validate_context_mode(value: Any) -> None:
    if not isinstance(value, str) or value not in CONTEXT_MODES:
        raise ValueError(f"run_manifest.json context_mode is not supported: {value}")


def _validate_seed(value: Any) -> None:
    _validate_non_negative_integer(value, "seed")


def _validate_trusted_fixture_provenance(manifest: dict[str, object]) -> None:
    scenario_sha256 = str(manifest["scenario_sha256"])
    trusted = _trusted_fixture_metadata().get(scenario_sha256)
    if trusted is None:
        raise ValueError("run_manifest.json scenario_sha256 does not match a trusted v0 fixture")
    for field_name in ("scenario_id", "fixture_type", "protocol", "context_mode", "seed"):
        if manifest[field_name] != trusted[field_name]:
            raise ValueError(f"run_manifest.json {field_name} does not match trusted fixture provenance")


def _trusted_fixture_metadata() -> dict[str, dict[str, object]]:
    fixtures: dict[str, dict[str, object]] = {}
    for fixture_path in sorted(_FIXTURE_DIR.glob("*.json")):
        scenario = load_scenario(fixture_path)
        scenario_sha256 = "sha256:" + hashlib.sha256(fixture_path.read_bytes()).hexdigest()
        fixtures[scenario_sha256] = {
            "path": fixture_path,
            "scenario_id": scenario["scenario_id"],
            "fixture_type": scenario["fixture_type"],
            "protocol": scenario["protocol"],
            "context_mode": scenario["context_mode"],
            "seed": scenario["seed"],
        }
    return fixtures


def _trusted_fixture_for_manifest(manifest: dict[str, object]) -> dict[str, object]:
    scenario_sha256 = str(manifest["scenario_sha256"])
    trusted = _trusted_fixture_metadata().get(scenario_sha256)
    if trusted is None:
        raise ValueError("run_manifest.json scenario_sha256 does not match a trusted v0 fixture")
    return trusted


def _validate_run_artifacts_match_trusted_fixture(run_root: Path, manifest: dict[str, object]) -> None:
    trusted = _trusted_fixture_for_manifest(manifest)
    run_id = str(manifest["run_id"])
    with tempfile.TemporaryDirectory() as expected_dir:
        expected_root = Path(expected_dir) / "expected-run"
        run_scenario(Path(str(trusted["path"])), expected_root, run_id=run_id)
        for relative_path in (*INITIAL_ARTIFACT_PATHS, *CANDIDATE_ARTIFACT_PATHS):
            actual_path = run_root / relative_path
            expected_path = expected_root / relative_path
            if not actual_path.is_file():
                raise FileNotFoundError(actual_path)
            if actual_path.read_bytes() != expected_path.read_bytes():
                raise ValueError(f"run artifact does not match trusted fixture output: {relative_path}")


def _remove_derived_outputs(run_root: Path) -> None:
    for relative_path in (*EVALUATOR_OUTPUT_PATHS, *REPORT_OUTPUT_PATHS):
        output_path = run_root / relative_path
        if output_path.exists():
            output_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
