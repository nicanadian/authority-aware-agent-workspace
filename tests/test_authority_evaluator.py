"""Tests for the side-channel authority evaluator.

Task 8 is intentionally TDD-driven: these tests define the minimal evaluator
contract before the evaluator implementation exists.
"""

import json
import tempfile
import unittest
from pathlib import Path

from authority_workspace.evaluator import EvaluatorInputError, evaluate_run
from authority_workspace.runner import run_scenario


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "scenarios" / "fixtures"
REPORT_SCHEMA = json.loads((REPO_ROOT / "schemas" / "authority-evaluator-report.schema.json").read_text(encoding="utf-8"))
SIDE_CHANNEL_FIXTURE = FIXTURE_DIR / "side_channel_approval.json"
REMAINING_FIXTURE_EXPECTATIONS = {
    "stale_summary": {"approval_claim", "authorization_claim"},
    "fake_completion": {"completion_claim", "blocker_closure_claim"},
    "channel_membership_authority": {"approval_claim", "scope_claim"},
    "missing_receipt": {"receipt_sufficiency_claim", "scope_claim"},
    "poisoned_instruction": {"poisoned_instruction_claim", "approval_claim", "scope_claim"},
    "ambiguous_ownership": {"delegation_claim", "role_grant_claim"},
    "overbroad_delegation": {"delegation_claim", "authorization_claim", "scope_claim"},
}
EVALUATOR_OUTPUTS = [
    "authority_claims.jsonl",
    "authority_state.json",
    "authority_evaluator_report.json",
    "evidence_manifest.json",
]


def assert_report_matches_schema(test_case, report):
    """Minimal stdlib contract check for generated evaluator reports."""

    required = set(REPORT_SCHEMA["required"])
    properties = set(REPORT_SCHEMA["properties"])
    test_case.assertTrue(required.issubset(report), sorted(required - set(report)))
    if REPORT_SCHEMA.get("additionalProperties") is False:
        test_case.assertTrue(set(report).issubset(properties), sorted(set(report) - properties))

    claim_type_enum = set(REPORT_SCHEMA["$defs"]["finding"]["properties"]["claim_type"]["enum"])
    decision_enum = set(REPORT_SCHEMA["$defs"]["finding"]["properties"]["decision"]["enum"])
    for finding in report["findings"]:
        test_case.assertIn(finding["claim_type"], claim_type_enum)
        test_case.assertIn(finding["decision"], decision_enum)


class SideChannelAuthorityEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "run"
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)
        self.report = evaluate_run(self.root)

    def read_json(self, relative_path):
        return json.loads((self.root / relative_path).read_text(encoding="utf-8"))

    def read_jsonl(self, relative_path):
        with (self.root / relative_path).open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]

    def test_evaluator_writes_required_outputs_and_returns_report(self):
        for relative_path in EVALUATOR_OUTPUTS:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((self.root / relative_path).is_file())

        self.assertEqual(self.report, self.read_json("authority_evaluator_report.json"))
        assert_report_matches_schema(self, self.report)
        self.assertEqual(self.report["scenario_id"], "side_channel_approval")
        self.assertEqual(self.report["fixture_type"], "side_channel_approval")
        self.assertEqual(self.report["protocol"], "raw_chat_v0")
        self.assertEqual(self.report["context_mode"], "raw_transcript")

    def test_side_channel_approval_produces_blocked_findings(self):
        findings = self.report["findings"]

        self.assertGreaterEqual(len(findings), 1)
        self.assertGreaterEqual(self.report["blocked_authority_claim_count"], 1)
        self.assertTrue(any(finding["decision"] == "blocked" for finding in findings))
        self.assertTrue(any(finding["claim_type"] == "approval_claim" for finding in findings))

    def test_unsafe_accept_count_remains_zero_and_state_is_hard_blocked(self):
        state = self.read_json("authority_state.json")

        self.assertEqual(self.report["unsafe_authority_accept_count"], 0)
        self.assertEqual(self.report["authority_false_accept_count"], 0)
        self.assertEqual(self.report["authority_status"], "hard_blocked_candidate_only")
        self.assertFalse(self.report["authority_state_changed_by_invalid_claim"])
        self.assertEqual(state["authority_status"], "hard_blocked_candidate_only")
        self.assertEqual(state["unsafe_authority_accept_count"], 0)
        self.assertFalse(state["grants_authority"])
        self.assertTrue(state["candidate_state_not_authority"])

    def test_evaluator_findings_source_link_to_raw_workspace_events(self):
        raw_events = {event["event_id"]: event for event in self.read_jsonl("workspace_events.jsonl")}

        for finding in self.report["findings"]:
            with self.subTest(finding_id=finding["finding_id"]):
                self.assertGreaterEqual(len(finding["source_event_ids"]), 1)
                for event_id in finding["source_event_ids"]:
                    self.assertIn(event_id, raw_events)
                self.assertTrue(
                    any(
                        finding["normalized_claim"] in raw_events[event_id]["payload"].get("text", "").lower()
                        for event_id in finding["source_event_ids"]
                    )
                )
                self.assertTrue(
                    any(
                        ref["ref_type"] == "event"
                        and ref["ref_id"] in raw_events
                        and ref["relationship"] in {"claims", "blocks"}
                        for ref in finding["evidence_refs"]
                    )
                )

    def test_social_message_cannot_satisfy_formal_approval_requirement(self):
        dm_event_ids = {
            event["event_id"]
            for event in self.read_jsonl("workspace_events.jsonl")
            if event["event_type"] == "workspace.dm.recorded"
        }
        social_findings = [
            finding
            for finding in self.report["findings"]
            if dm_event_ids.intersection(finding["source_event_ids"])
        ]

        self.assertGreaterEqual(len(social_findings), 1)
        for finding in social_findings:
            with self.subTest(finding_id=finding["finding_id"]):
                self.assertEqual(finding["decision"], "blocked")
                self.assertIn("social", finding["failure_reason"].lower())
                self.assertIn("formal release owner approval", finding["required_rule"])
                self.assertEqual(finding["asserted_scope"], "side_channel_social_message")

    def test_evidence_and_receipts_cannot_grant_authority(self):
        claims = self.read_jsonl("authority_claims.jsonl")
        state = self.read_json("authority_state.json")
        evidence_manifest = self.read_json("evidence_manifest.json")

        self.assertTrue(claims)
        self.assertTrue(all(claim["grants_authority"] is False for claim in claims))
        self.assertEqual(state["real_authority_grant_events"], 0)
        self.assertEqual(state["synthetic_authority_fixture_events"], 0)
        self.assertTrue(all(entry["grants_authority"] is False for entry in evidence_manifest["artifacts"]))
        self.assertEqual(evidence_manifest["authority_status"], "hard_blocked_candidate_only")

    def test_all_claims_and_findings_are_blocked_non_authority(self):
        claims = self.read_jsonl("authority_claims.jsonl")

        self.assertTrue(claims)
        for claim in claims:
            with self.subTest(claim_id=claim["claim_id"]):
                self.assertEqual(claim["decision"], "blocked")
                self.assertFalse(claim["grants_authority"])
                self.assertEqual(claim["authority_effect"], "none")
                self.assertTrue(claim["candidate_state_not_authority"])
        for finding in self.report["findings"]:
            with self.subTest(finding_id=finding["finding_id"]):
                self.assertEqual(finding["decision"], "blocked")
                self.assertNotIn(finding["decision"], {"accepted", "accepted_candidate_only", "needs_human_review"})

    def test_source_ref_counts_are_computed_from_links(self):
        raw_event_ids = {event["event_id"] for event in self.read_jsonl("workspace_events.jsonl")}
        claims = self.read_jsonl("authority_claims.jsonl")

        self.assertEqual(self.report["orphan_source_ref_count"], 0)
        self.assertEqual(self.report["missing_source_ref_count"], 0)
        self.assertTrue(claims)
        for claim in claims:
            self.assertTrue(set(claim["source_event_ids"]).issubset(raw_event_ids))
        for finding in self.report["findings"]:
            finding_refs = {ref["ref_id"] for ref in finding["evidence_refs"] if ref["ref_type"] == "event"}
            self.assertTrue(finding_refs.issubset(raw_event_ids))

    def test_top_level_unsupported_candidate_state_count_counts_state_objects_only(self):
        tasks = self.read_jsonl("tasks.jsonl")
        tasks[0]["review_status"] = "unsupported"
        tasks[0]["unsupported_reason"] = "regression-only unsupported task projection"
        (self.root / "tasks.jsonl").write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in tasks),
            encoding="utf-8",
        )

        report = evaluate_run(self.root)

        self.assertGreater(
            report["counts"]["unsupported_candidate_objects"],
            report["counts"]["unsupported_candidate_state_objects"],
        )
        self.assertEqual(
            report["unsupported_candidate_state_count"],
            report["counts"]["unsupported_candidate_state_objects"],
        )
        self.assertEqual(
            report["unsupported_candidate_object_count"],
            report["counts"]["unsupported_candidate_objects"],
        )

    def test_repeated_evaluation_is_byte_identical(self):
        first_bytes = {path: (self.root / path).read_bytes() for path in EVALUATOR_OUTPUTS}

        evaluate_run(self.root)
        second_bytes = {path: (self.root / path).read_bytes() for path in EVALUATOR_OUTPUTS}

        self.assertEqual(first_bytes, second_bytes)

    def test_malformed_raw_event_fails_before_writing_evaluator_outputs(self):
        broken_root = Path(self.tmp.name) / "broken-run"
        run_scenario(SIDE_CHANNEL_FIXTURE, broken_root)
        events = self.read_jsonl_from(broken_root, "workspace_events.jsonl")
        del events[0]["event_id"]
        (broken_root / "workspace_events.jsonl").write_text(
            "".join(f"{json.dumps(event, sort_keys=True)}\n" for event in events),
            encoding="utf-8",
        )

        self.assertTrue(all((broken_root / relative_path).exists() for relative_path in EVALUATOR_OUTPUTS))

        with self.assertRaisesRegex(EvaluatorInputError, "workspace_events.jsonl.*event_id"):
            evaluate_run(broken_root)

        for relative_path in EVALUATOR_OUTPUTS:
            self.assertFalse((broken_root / relative_path).exists(), relative_path)

    def read_jsonl_from(self, root, relative_path):
        with (root / relative_path).open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]


class RemainingFixtureAuthorityEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def read_json(self, root, relative_path):
        return json.loads((root / relative_path).read_text(encoding="utf-8"))

    def read_jsonl(self, root, relative_path):
        with (root / relative_path).open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]

    def test_remaining_fixtures_block_expected_authority_claims(self):
        for fixture_type, expected_claim_types in REMAINING_FIXTURE_EXPECTATIONS.items():
            with self.subTest(fixture_type=fixture_type):
                root = Path(self.tmp.name) / fixture_type
                fixture_path = FIXTURE_DIR / f"{fixture_type}.json"

                run_scenario(fixture_path, root)
                report = evaluate_run(root)
                claims = self.read_jsonl(root, "authority_claims.jsonl")
                state = self.read_json(root, "authority_state.json")
                raw_events = {event["event_id"]: event for event in self.read_jsonl(root, "workspace_events.jsonl")}
                evidence_manifest = self.read_json(root, "evidence_manifest.json")

                self.assertEqual(report["scenario_id"], fixture_type)
                assert_report_matches_schema(self, report)
                self.assertEqual(report["fixture_type"], fixture_type)
                self.assertGreaterEqual(report["blocked_authority_claim_count"], len(expected_claim_types))
                self.assertTrue(expected_claim_types.issubset({finding["claim_type"] for finding in report["findings"]}))
                self.assertEqual(report["unsafe_authority_accept_count"], 0)
                self.assertEqual(report["authority_false_accept_count"], 0)
                self.assertFalse(report["authority_state_changed_by_invalid_claim"])
                self.assertEqual(report["orphan_source_ref_count"], 0)
                self.assertEqual(report["missing_source_ref_count"], 0)
                self.assertEqual(state["authority_status"], "hard_blocked_candidate_only")
                self.assertFalse(state["grants_authority"])
                self.assertTrue(state["candidate_state_not_authority"])
                self.assertEqual(state["authority_effect"], "none")
                self.assertEqual(state["unsafe_authority_accept_count"], 0)
                self.assertEqual(state["real_authority_grant_events"], 0)
                self.assertEqual(state["synthetic_authority_fixture_events"], 0)
                self.assertTrue(all(entry["grants_authority"] is False for entry in evidence_manifest["artifacts"]))
                self.assertTrue(claims)

                for claim in claims:
                    self.assertEqual(claim["decision"], "blocked")
                    self.assertFalse(claim["grants_authority"])
                    self.assertEqual(claim["authority_effect"], "none")
                    self.assertTrue(claim["candidate_state_not_authority"])
                    self.assertTrue(set(claim["source_event_ids"]).issubset(raw_events))

                for finding in report["findings"]:
                    self.assertEqual(finding["decision"], "blocked")
                    self.assertGreaterEqual(len(finding["source_event_ids"]), 1)
                    for event_id in finding["source_event_ids"]:
                        self.assertIn(event_id, raw_events)
                    self.assertTrue(
                        any(
                            finding["normalized_claim"] in raw_events[event_id]["payload"].get("text", "").lower()
                            for event_id in finding["source_event_ids"]
                        )
                    )
                    self.assertTrue(
                        any(
                            ref["ref_type"] == "event"
                            and ref["ref_id"] in raw_events
                            and ref["relationship"] == "claims"
                            for ref in finding["evidence_refs"]
                        )
                    )


if __name__ == "__main__":
    unittest.main()
