"""Deterministic local command-line interface for authority workspace runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from authority_workspace.artifacts import build_manifest_entries, write_json
from authority_workspace.evaluator import evaluate_run
from authority_workspace.report import generate_report
from authority_workspace.runner import CANDIDATE_ARTIFACT_PATHS, INITIAL_ARTIFACT_PATHS, RUN_ARTIFACT_PATHS, run_scenario


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
    _rewrite_manifest(run_root, (*INITIAL_ARTIFACT_PATHS, *CANDIDATE_ARTIFACT_PATHS))
    evaluate_run(run_root)
    generate_report(run_root)
    manifest = _rewrite_manifest(run_root, RUN_ARTIFACT_PATHS)
    print(f"evaluated run: {run_root}")
    print(f"scenario_id: {manifest['scenario_id']}")
    return 0


def _rewrite_manifest(run_root: Path, artifact_paths: Sequence[str]) -> dict[str, object]:
    manifest_path = run_root / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"] = build_manifest_entries(run_root, artifact_paths)
    write_json(run_root, "run_manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
