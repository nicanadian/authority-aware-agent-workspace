"""Command-line interface tests."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from authority_workspace.cli import main
from authority_workspace.runner import RUN_ARTIFACT_PATHS, run_scenario


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDE_CHANNEL_FIXTURE = REPO_ROOT / "scenarios" / "fixtures" / "side_channel_approval.json"


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def read_json(self, root, relative_path):
        return json.loads((root / relative_path).read_text(encoding="utf-8"))

    def artifact_bytes(self, root):
        return {path: (root / path).read_bytes() for path in ["run_manifest.json", *RUN_ARTIFACT_PATHS]}

    def test_main_returns_nonzero_for_invalid_command(self):
        self.assertNotEqual(main(["not-a-command"]), 0)

    def test_run_returns_nonzero_when_scenario_is_missing(self):
        missing = self.root / "missing.json"
        out = self.root / "run"

        self.assertNotEqual(main(["run", str(missing), "--out", str(out)]), 0)
        self.assertFalse((out / "run_manifest.json").exists())

    def test_run_writes_all_artifacts(self):
        out = self.root / "run"

        self.assertEqual(main(["run", str(SIDE_CHANNEL_FIXTURE), "--out", str(out)]), 0)

        for relative_path in ["run_manifest.json", *RUN_ARTIFACT_PATHS]:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((out / relative_path).is_file())
        manifest = self.read_json(out, "run_manifest.json")
        self.assertEqual(manifest["scenario_id"], "side_channel_approval")
        self.assertEqual([entry["path"] for entry in manifest["artifacts"]], list(RUN_ARTIFACT_PATHS))

    def test_evaluate_reads_existing_run_and_preserves_deterministic_outputs(self):
        run_root = self.root / "run"
        run_scenario(SIDE_CHANNEL_FIXTURE, run_root)
        before = self.artifact_bytes(run_root)

        self.assertEqual(main(["evaluate", str(run_root)]), 0)

        self.assertEqual(self.artifact_bytes(run_root), before)
        manifest = self.read_json(run_root, "run_manifest.json")
        report = self.read_json(run_root, "authority_evaluator_report.json")
        state = self.read_json(run_root, "authority_state.json")
        self.assertEqual(report["scenario_id"], manifest["scenario_id"])
        self.assertEqual(state["authority_status"], "hard_blocked_candidate_only")
        self.assertEqual([entry["path"] for entry in manifest["artifacts"]], list(RUN_ARTIFACT_PATHS))

    def test_evaluate_recomputes_manifest_before_scoring(self):
        run_root = self.root / "run"
        run_scenario(SIDE_CHANNEL_FIXTURE, run_root)
        manifest = self.read_json(run_root, "run_manifest.json")
        for entry in manifest["artifacts"]:
            if entry["path"] == "workspace_events.jsonl":
                entry["jsonl_line_count"] = 999
        (run_root / "run_manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")

        self.assertEqual(main(["evaluate", str(run_root)]), 0)

        final_manifest = self.read_json(run_root, "run_manifest.json")
        report = self.read_json(run_root, "authority_evaluator_report.json")
        workspace_entry = next(entry for entry in final_manifest["artifacts"] if entry["path"] == "workspace_events.jsonl")
        self.assertEqual(workspace_entry["jsonl_line_count"], 4)
        self.assertEqual(report["counts"]["raw_events_scored"], 4)

    def test_evaluate_returns_nonzero_for_missing_run(self):
        self.assertNotEqual(main(["evaluate", str(self.root / "missing-run")]), 0)

    def test_cli_smoke_uses_temporary_directory(self):
        run_root = self.root / "side_channel_smoke"
        run_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "authority_workspace.cli",
                "run",
                str(SIDE_CHANNEL_FIXTURE),
                "--out",
                str(run_root),
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(run_result.returncode, 0, run_result.stderr)

        evaluate_result = subprocess.run(
            [sys.executable, "-m", "authority_workspace.cli", "evaluate", str(run_root)],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(evaluate_result.returncode, 0, evaluate_result.stderr)
        self.assertTrue((run_root / "run_report.md").is_file())


if __name__ == "__main__":
    unittest.main()
