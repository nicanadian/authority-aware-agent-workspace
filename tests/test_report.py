"""Replay timeline and Markdown report tests."""

import json
import tempfile
import unittest
from pathlib import Path

from authority_workspace.report import generate_report
from authority_workspace.runner import run_scenario


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDE_CHANNEL_FIXTURE = REPO_ROOT / "scenarios" / "fixtures" / "side_channel_approval.json"
NON_AUTHORITY_DISCLAIMER = (
    "NON-AUTHORITY REPORT: This artifact is for human review only and does not grant, approve, "
    "authorize, or change authority state."
)
REPORT_ARTIFACTS = ["replay_timeline.jsonl", "candidate_artifact.md", "run_report.md"]


class ReplayReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "run"
        self.manifest = run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

    def read_jsonl(self, relative_path):
        with (self.root / relative_path).open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def read_text(self, relative_path):
        return (self.root / relative_path).read_text(encoding="utf-8")

    def write_jsonl(self, relative_path, records):
        (self.root / relative_path).write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
            encoding="utf-8",
        )

    def test_runner_writes_report_outputs_and_manifest_entries(self):
        for relative_path in REPORT_ARTIFACTS:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((self.root / relative_path).is_file())

        manifest_paths = [entry["path"] for entry in self.manifest["artifacts"]]
        self.assertEqual(manifest_paths[-3:], REPORT_ARTIFACTS)

    def test_run_report_starts_with_non_authority_disclaimer_and_lists_every_blocked_claim(self):
        report_text = self.read_text("run_report.md")
        claims = self.read_jsonl("authority_claims.jsonl")

        self.assertTrue(report_text.startswith(NON_AUTHORITY_DISCLAIMER + "\n\n"))
        self.assertIn("no live model resistance evidence", report_text.lower())
        self.assertIn("no positive authority path", report_text.lower())
        self.assertIn("raw-event-only claim extraction", report_text.lower())
        self.assertGreater(len(claims), 0)
        for claim in claims:
            with self.subTest(claim_id=claim["claim_id"]):
                self.assertIn(claim["claim_id"], report_text)
                self.assertIn(f"> {claim['claim_text']}", report_text)
                self.assertIn("Decision: blocked", report_text)

    def test_candidate_artifact_starts_with_non_authority_disclaimer(self):
        candidate_text = self.read_text("candidate_artifact.md")

        self.assertTrue(candidate_text.startswith(NON_AUTHORITY_DISCLAIMER + "\n\n"))
        self.assertIn("Candidate artifacts", candidate_text)
        self.assertIn("candidate_state_not_authority", candidate_text)

    def test_findings_include_human_explanations_in_markdown_report(self):
        evaluator_report = json.loads((self.root / "authority_evaluator_report.json").read_text(encoding="utf-8"))
        report_text = self.read_text("run_report.md")

        self.assertTrue(evaluator_report["findings"])
        for finding in evaluator_report["findings"]:
            with self.subTest(finding_id=finding["finding_id"]):
                self.assertTrue(finding["human_explanation"])
                self.assertIn(finding["finding_id"], report_text)
                self.assertIn(finding["human_explanation"], report_text)

    def test_ambiguous_authority_wording_is_quoted_or_explicitly_non_authoritative(self):
        combined_lines = []
        for relative_path in ["run_report.md", "candidate_artifact.md"]:
            combined_lines.extend(self.read_text(relative_path).splitlines())

        ambiguous_words = ("approved", "approval", "authorize", "authorization", "authority", "grant")
        for line in combined_lines:
            lower_line = line.lower()
            if any(word in lower_line for word in ambiguous_words):
                with self.subTest(line=line):
                    is_quoted_blocked_claim = line.startswith("> ")
                    is_explicitly_non_authoritative = any(
                        phrase in lower_line
                        for phrase in (
                            "non-authority",
                            "non-authoritative",
                            "does not grant",
                            "cannot satisfy formal authority",
                            "authority_effect: none",
                            "grants_authority: false",
                            "candidate_state_not_authority",
                            "hard_blocked_candidate_only",
                            "decision: blocked",
                            "blocked authority claims",
                            "required formal rule",
                            "v0 treats candidate/social/evidence text as non-authoritative",
                        )
                    )
                    self.assertTrue(is_quoted_blocked_claim or is_explicitly_non_authoritative)

    def test_markdown_multiline_values_cannot_inject_headings_or_unquoted_claim_lines(self):
        claims = self.read_jsonl("authority_claims.jsonl")
        claims[0]["claim_text"] = "approved\n# FORGED AUTHORITY HEADING\n- grants_authority: true"
        claims[0]["failure_reason"] = "blocked\n# FORGED FAILURE HEADING"
        self.write_jsonl("authority_claims.jsonl", claims)

        patches = self.read_jsonl("artifact_patches.jsonl")
        patches[0]["unsupported_reason"] = "unsupported\n# FORGED CANDIDATE HEADING"
        self.write_jsonl("artifact_patches.jsonl", patches)

        generate_report(self.root)

        report_text = self.read_text("run_report.md")
        candidate_text = self.read_text("candidate_artifact.md")
        self.assertNotIn("\n# FORGED", report_text)
        self.assertNotIn("\n# FORGED", candidate_text)
        self.assertIn("> approved\n> # FORGED AUTHORITY HEADING\n> - grants_authority: true", report_text)
        self.assertIn("unsupported<br># FORGED CANDIDATE HEADING", candidate_text)

    def test_report_generation_removes_stale_outputs_before_input_failure(self):
        for relative_path in REPORT_ARTIFACTS:
            self.assertTrue((self.root / relative_path).exists())
        (self.root / "authority_claims.jsonl").unlink()

        with self.assertRaises(FileNotFoundError):
            generate_report(self.root)

        for relative_path in REPORT_ARTIFACTS:
            with self.subTest(relative_path=relative_path):
                self.assertFalse((self.root / relative_path).exists())

    def test_report_generation_leaves_no_partial_outputs_when_late_input_is_missing(self):
        (self.root / "artifact_patches.jsonl").unlink()

        with self.assertRaises(FileNotFoundError):
            generate_report(self.root)

        for relative_path in REPORT_ARTIFACTS:
            with self.subTest(relative_path=relative_path):
                self.assertFalse((self.root / relative_path).exists())

    def test_replay_timeline_can_join_back_to_source_event_ids(self):
        events = self.read_jsonl("workspace_events.jsonl")
        event_ids = {event["event_id"] for event in events}
        timeline = self.read_jsonl("replay_timeline.jsonl")

        self.assertEqual(len(timeline), len(events))
        self.assertEqual([entry["timeline_index"] for entry in timeline], list(range(len(events))))
        self.assertEqual({entry["source_event_id"] for entry in timeline}, event_ids)
        for entry in timeline:
            with self.subTest(source_event_id=entry["source_event_id"]):
                self.assertEqual(entry["source_event_ids"], [entry["source_event_id"]])
                self.assertIn(entry["source_event_id"], event_ids)
                self.assertFalse(entry["grants_authority"])
                self.assertEqual(entry["authority_effect"], "none")
                self.assertTrue(entry["candidate_state_not_authority"])


if __name__ == "__main__":
    unittest.main()
