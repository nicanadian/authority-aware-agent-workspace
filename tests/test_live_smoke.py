"""Tests for bounded live-smoke plumbing."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from authority_workspace.live_smoke import LIVE_SMOKE_OUTPUT_PATHS, run_live_smoke
from authority_workspace.cli import main


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDE_CHANNEL_FIXTURE = REPO_ROOT / "scenarios" / "fixtures" / "side_channel_approval.json"


class LiveSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def read_json(self, root: Path, relative_path: str):
        return json.loads((root / relative_path).read_text(encoding="utf-8"))

    def read_jsonl(self, root: Path, relative_path: str):
        with (root / relative_path).open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]

    def provider_command(self, body) -> list[str]:
        body_json = json.dumps(body, sort_keys=True)
        code = (
            "import json,sys; "
            "payload=json.load(sys.stdin); "
            f"body=json.loads({body_json!r}); "
            "print(json.dumps({'decision_text': body, 'saw_context_sha256': payload['context_sha256']}, sort_keys=True))"
        )
        return [sys.executable, "-c", code]

    def test_live_smoke_runs_one_bounded_provider_call_and_evaluates_outputs(self):
        run_root = self.root / "live"
        manifest = run_live_smoke(
            SIDE_CHANNEL_FIXTURE,
            run_root,
            provider_command=self.provider_command("social approval is not authority"),
            timeout_seconds=5,
            max_context_bytes=4096,
        )

        artifact_paths = [entry["path"] for entry in manifest["artifacts"]]
        for path in LIVE_SMOKE_OUTPUT_PATHS:
            self.assertIn(path, artifact_paths)
        trace = self.read_json(run_root, "live_smoke_trace.json")
        outputs = self.read_jsonl(run_root, "live_model_outputs.jsonl")
        report = self.read_json(run_root, "authority_evaluator_report.json")
        evidence = self.read_json(run_root, "evidence_manifest.json")

        self.assertEqual(trace["call_count"], 1)
        self.assertTrue(trace["bounded"])
        self.assertEqual(trace["provider_exit_code"], 0)
        self.assertLessEqual(trace["prompt_bytes"], 4096)
        self.assertEqual(outputs[0]["authority_effect"], "none")
        self.assertFalse(outputs[0]["grants_authority"])
        self.assertTrue(outputs[0]["candidate_state_not_authority"])
        self.assertEqual(outputs[0]["source_context_sha256"], trace["context_sha256"])
        self.assertIn("live_smoke_trace.json", [entry["path"] for entry in evidence["artifacts"]])
        self.assertEqual(report["unsafe_authority_accept_count"], 0)

    def test_live_smoke_rejects_unbounded_prompt_before_provider_call(self):
        with self.assertRaisesRegex(ValueError, "max_context_bytes"):
            run_live_smoke(
                SIDE_CHANNEL_FIXTURE,
                self.root / "too-small",
                provider_command=self.provider_command("unused"),
                timeout_seconds=5,
                max_context_bytes=1,
            )

    def test_live_smoke_rejects_failing_provider_without_authority_outputs(self):
        run_root = self.root / "fail"
        with self.assertRaisesRegex(RuntimeError, "provider command failed"):
            run_live_smoke(
                SIDE_CHANNEL_FIXTURE,
                run_root,
                provider_command=[sys.executable, "-c", "import sys; sys.exit(7)"],
                timeout_seconds=5,
                max_context_bytes=4096,
            )
        self.assertFalse((run_root / "live_model_outputs.jsonl").exists())

    def test_live_smoke_provider_authority_claim_is_scanned_but_blocked(self):
        run_root = self.root / "claim"
        run_live_smoke(
            SIDE_CHANNEL_FIXTURE,
            run_root,
            provider_command=self.provider_command("release-candidate-7 is approved for publication"),
            timeout_seconds=5,
            max_context_bytes=4096,
        )
        report = self.read_json(run_root, "authority_evaluator_report.json")
        claims = self.read_jsonl(run_root, "authority_claims.jsonl")
        self.assertGreaterEqual(report["derived_claims_detected_count"], 1)
        self.assertEqual(report["unsafe_authority_accept_count"], 0)
        self.assertTrue(any(claim.get("source_artifact_path") == "live_model_outputs.jsonl" for claim in claims))

    def test_live_smoke_scans_authority_shaped_provider_output_fields(self):
        run_root = self.root / "claim-field"
        command = self.provider_command({"authority_effect": "release-candidate-7 is approved for publication"})
        run_live_smoke(
            SIDE_CHANNEL_FIXTURE,
            run_root,
            provider_command=command,
            timeout_seconds=5,
            max_context_bytes=4096,
        )
        claims = self.read_jsonl(run_root, "authority_claims.jsonl")
        self.assertTrue(any(claim.get("source_artifact_path") == "live_model_outputs.jsonl" for claim in claims))

    def test_live_smoke_failure_clears_stale_live_outputs(self):
        run_root = self.root / "reuse"
        run_live_smoke(
            SIDE_CHANNEL_FIXTURE,
            run_root,
            provider_command=self.provider_command("first success"),
            timeout_seconds=5,
            max_context_bytes=4096,
        )
        self.assertTrue((run_root / "live_model_outputs.jsonl").exists())

        with self.assertRaisesRegex(RuntimeError, "provider command failed"):
            run_live_smoke(
                SIDE_CHANNEL_FIXTURE,
                run_root,
                provider_command=[sys.executable, "-c", "import sys; sys.exit(7)"],
                timeout_seconds=5,
                max_context_bytes=4096,
            )
        self.assertFalse((run_root / "live_model_outputs.jsonl").exists())

    def test_cli_live_smoke_requires_explicit_provider_command(self):
        run_root = self.root / "cli-live"
        exit_code = main(["live-smoke", str(SIDE_CHANNEL_FIXTURE), "--out", str(run_root)])
        self.assertNotEqual(exit_code, 0)
        self.assertFalse((run_root / "live_model_outputs.jsonl").exists())

    def test_cli_live_smoke_accepts_provider_command(self):
        run_root = self.root / "cli-live-ok"
        command = json.dumps(self.provider_command("cli bounded response"))
        exit_code = main([
            "live-smoke",
            str(SIDE_CHANNEL_FIXTURE),
            "--out",
            str(run_root),
            "--provider-command-json",
            command,
            "--timeout-seconds",
            "5",
            "--max-context-bytes",
            "4096",
        ])
        self.assertEqual(exit_code, 0)
        self.assertTrue((run_root / "live_smoke_trace.json").is_file())
        self.assertTrue((run_root / "live_model_outputs.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
