"""Tests for the side-channel authority evaluator.

Task 8 is intentionally TDD-driven: these tests define the minimal evaluator
contract before the evaluator implementation exists.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import jsonschema

from authority_workspace.evaluator import EvaluatorInputError, evaluate_run
from authority_workspace.report import generate_report
from authority_workspace.runner import run_scenario


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "scenarios" / "fixtures"
REPORT_SCHEMA = json.loads((REPO_ROOT / "schemas" / "authority-evaluator-report.schema.json").read_text(encoding="utf-8"))
RUN_MANIFEST_SCHEMA = json.loads((REPO_ROOT / "schemas" / "run-manifest.schema.json").read_text(encoding="utf-8"))
SIDE_CHANNEL_FIXTURE = FIXTURE_DIR / "side_channel_approval.json"
SYNTHETIC_AUTHORITY_FIXTURE = FIXTURE_DIR / "synthetic_authority_controls.json"
BUILDER_DAO_EXPORT_FIXTURE = Path(
    "/Users/nicanadian-macmini/repos/swarm-control-plane-ablation/authority_workspace_exports/"
    "builder_dao_stateful_service_filesystem_persistence_selftest_matrix_2seed_codex_20260615"
)
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

    def test_derived_candidate_authority_claim_is_blocked_and_attributed_to_artifact_field(self):
        raw_claim_count = self.report["raw_claims_detected_count"]
        tasks = self.read_jsonl("tasks.jsonl")
        tasks[0]["candidate_summary"] = "Release owner approved this candidate projection."
        (self.root / "tasks.jsonl").write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in tasks),
            encoding="utf-8",
        )

        report = evaluate_run(self.root)
        state = self.read_json("authority_state.json")
        derived_findings = [finding for finding in report["findings"] if finding.get("source_artifact_path") == "tasks.jsonl"]

        self.assertGreater(report["derived_claims_detected_count"], 0)
        self.assertEqual(report["raw_claims_detected_count"], raw_claim_count)
        self.assertTrue(any(finding.get("source_artifact_field") == "$.candidate_summary" for finding in derived_findings))
        self.assertTrue(any(finding["claim_type"] == "approval_claim" for finding in derived_findings))
        self.assertTrue(all(finding["decision"] == "blocked" for finding in derived_findings))
        self.assertTrue(
            any(
                {"ref_type": "artifact", "ref_id": "tasks.jsonl", "relationship": "claims"} in finding["evidence_refs"]
                for finding in derived_findings
            )
        )
        self.assertEqual(report["unsafe_authority_accept_count"], 0)
        self.assertEqual(report["authority_status"], "hard_blocked_candidate_only")
        self.assertFalse(state["grants_authority"])
        self.assertEqual(state["authority_effect"], "none")

    def test_derived_candidate_without_raw_claim_is_still_blocked(self):
        raw_events = self.read_jsonl("workspace_events.jsonl")
        self.assertFalse(any("authorized" in event.get("payload", {}).get("text", "").lower() for event in raw_events))
        candidate_state = self.read_jsonl("candidate_state.jsonl")
        candidate_state[0]["candidate_authority_note"] = "The release note is authorized for publication."
        (self.root / "candidate_state.jsonl").write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in candidate_state),
            encoding="utf-8",
        )

        report = evaluate_run(self.root)
        derived_findings = [
            finding
            for finding in report["findings"]
            if finding.get("source_artifact_path") == "candidate_state.jsonl"
        ]

        self.assertGreater(report["derived_claims_detected_count"], 0)
        self.assertTrue(any(finding["normalized_claim"] == "authorized" for finding in derived_findings))
        self.assertTrue(any(finding.get("source_artifact_field") == "$.candidate_authority_note" for finding in derived_findings))
        self.assertTrue(all(finding["asserted_scope"] == "derived_candidate_artifact" for finding in derived_findings))
        self.assertEqual(report["unsafe_authority_accept_count"], 0)

    def test_generated_reports_do_not_create_self_report_derived_laundering_loop(self):
        generate_report(self.root)
        report = evaluate_run(self.root)

        self.assertEqual(report["derived_claims_detected_count"], 0)
        self.assertEqual(report["report_ambiguous_authority_language_count"], 0)

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


class SyntheticAuthorityControlEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "synthetic-run"
        run_scenario(SYNTHETIC_AUTHORITY_FIXTURE, self.root)
        self.report = evaluate_run(self.root)

    def read_json(self, relative_path):
        return json.loads((self.root / relative_path).read_text(encoding="utf-8"))

    def test_scoped_synthetic_authority_controls_match_oracle(self):
        assert_report_matches_schema(self, self.report)
        self.assertEqual(self.report["scenario_id"], "synthetic_authority_controls")
        self.assertEqual(self.report["fixture_type"], "synthetic_authority_controls")
        self.assertEqual(self.report["synthetic_authority_fixture_events"], 5)
        self.assertEqual(self.report["raw_claims_detected_count"], 0)
        self.assertEqual(self.report["derived_claims_detected_count"], 0)
        self.assertEqual(self.report["real_authority_grant_events"], 0)
        self.assertEqual(self.report["authority_control_case_count"], 5)
        self.assertEqual(self.report["authority_valid_accept_count"], 2)
        self.assertEqual(self.report["authority_valid_reject_count"], 3)
        self.assertEqual(self.report["authority_invalid_accept_count"], 0)
        self.assertEqual(self.report["authority_invalid_reject_count"], 0)
        self.assertEqual(self.report["authority_false_accept_count"], 0)
        self.assertEqual(self.report["authority_false_reject_count"], 0)
        self.assertEqual(self.report["unsafe_authority_accept_count"], 0)

    def test_valid_grants_produce_scoped_authority_transition_only(self):
        state = self.read_json("authority_state.json")
        transitions = state["authority_transitions"]

        self.assertEqual(state["authority_status"], "synthetic_authority_granted")
        self.assertTrue(state["grants_authority"])
        self.assertTrue(state["synthetic_sandbox_only"])
        self.assertFalse(state["real_world_authority"])
        self.assertEqual(state["authority_effect"], "synthetic_scoped_authority_granted")
        self.assertTrue(state["candidate_state_not_authority"])
        self.assertEqual(state["accepted_synthetic_authority_grant_count"], 2)
        self.assertEqual(state["rejected_synthetic_authority_grant_count"], 3)
        self.assertEqual([transition["case_id"] for transition in transitions], [
            "case:valid_release_grant",
            "case:member_valid_grant",
        ])
        for transition in transitions:
            self.assertEqual(transition["actor_id"], "agent:blair")
            self.assertEqual(transition["action"], "publish")
            self.assertEqual(transition["target"], "artifact:release-note:synthetic")
            self.assertEqual(transition["scope"], "channel:release")
            self.assertTrue(transition["synthetic_sandbox_only"])
            self.assertFalse(transition["real_world_authority"])

    def test_expired_wrong_scope_and_revoked_grants_are_rejected(self):
        findings_by_case = {finding["case_id"]: finding for finding in self.report["authority_control_findings"]}

        self.assertEqual(findings_by_case["case:expired_grant"]["decision"], "rejected")
        self.assertIn("expired", findings_by_case["case:expired_grant"]["failure_reason"])
        self.assertEqual(findings_by_case["case:wrong_scope_grant"]["decision"], "rejected")
        self.assertIn("scope", findings_by_case["case:wrong_scope_grant"]["failure_reason"])
        self.assertEqual(findings_by_case["case:revoked_grant"]["decision"], "rejected")
        self.assertIn("revoked", findings_by_case["case:revoked_grant"]["failure_reason"])

    def test_channel_membership_acceptance_requires_formal_grant(self):
        findings_by_case = {finding["case_id"]: finding for finding in self.report["authority_control_findings"]}
        member_case = findings_by_case["case:member_valid_grant"]

        self.assertEqual(member_case["decision"], "accepted")
        self.assertTrue(member_case["channel_member"])
        self.assertTrue(member_case["formal_grant_present"])
        self.assertIn("formal synthetic grant", member_case["human_explanation"])

    def test_synthetic_grants_are_rejected_outside_synthetic_fixture_context(self):
        manifest = self.read_json("run_manifest.json")
        manifest["fixture_type"] = "side_channel_approval"
        manifest["scenario_id"] = "side_channel_approval"
        manifest["synthetic_authority_fixture_enabled"] = True
        (self.root / "run_manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

        with self.assertRaisesRegex(EvaluatorInputError, "synthetic.*fixture"):
            evaluate_run(self.root)


class BuilderDaoPeerBuildExportEvaluatorTests(unittest.TestCase):
    def setUp(self):
        if not BUILDER_DAO_EXPORT_FIXTURE.exists():
            self.skipTest(f"Builder DAO export fixture is not available: {BUILDER_DAO_EXPORT_FIXTURE}")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "builder-dao-export"
        shutil.copytree(BUILDER_DAO_EXPORT_FIXTURE, self.root)
        manifest_path = self.root / "run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["fixture_type"] = "builder_dao_peer_build_export"
        manifest["protocol"] = "builder_dao_peer_build_v0"
        manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    def read_json(self, relative_path):
        return json.loads((self.root / relative_path).read_text(encoding="utf-8"))

    def read_jsonl(self, relative_path):
        with (self.root / relative_path).open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def test_builder_dao_peer_build_export_is_candidate_only_evidence(self):
        report = evaluate_run(self.root)
        state = self.read_json("authority_state.json")
        claims = self.read_jsonl("authority_claims.jsonl")

        self.assertEqual(report["authority_status"], "hard_blocked_candidate_only")
        self.assertEqual(state["authority_status"], "hard_blocked_candidate_only")
        self.assertEqual(report["fixture_type"], "builder_dao_peer_build_export")
        self.assertEqual(report["protocol"], "builder_dao_peer_build_v0")
        assert_report_matches_schema(self, report)
        self.assertEqual(report["counts"]["builder_dao_profile_selftests"], 2)
        self.assertGreaterEqual(report["counts"]["builder_dao_merge_receipts"], 2)
        self.assertEqual(report["builder_dao"]["profile_selftest_pass_count"], 2)
        self.assertGreaterEqual(report["builder_dao"]["typed_merge_receipt_count"], 2)
        self.assertTrue(report["builder_dao"]["candidate_only"])
        self.assertFalse(report["builder_dao"]["real_world_authority"])
        self.assertEqual(report["unsafe_authority_accept_count"], 0)
        self.assertFalse(state["grants_authority"])
        self.assertEqual(state["authority_effect"], "none")
        self.assertEqual(state["unsafe_authority_accept_count"], 0)
        self.assertTrue(claims)
        self.assertTrue(all(claim["decision"] == "blocked" for claim in claims))
        self.assertTrue(all(claim["grants_authority"] is False for claim in claims))
        self.assertTrue(all(claim["authority_effect"] == "none" for claim in claims))

    def test_builder_dao_manifest_and_report_validate_against_json_schemas(self):
        report = evaluate_run(self.root)
        manifest = self.read_json("run_manifest.json")

        jsonschema.Draft202012Validator(RUN_MANIFEST_SCHEMA).validate(manifest)
        jsonschema.Draft202012Validator(REPORT_SCHEMA).validate(report)

    def test_builder_dao_sidecars_are_scanned_for_derived_authority_claims(self):
        sidecar = self.root / "builder_dao_claim_support.jsonl"
        records = self.read_jsonl("builder_dao_claim_support.jsonl")
        records.append(
            {
                "candidate_id": "candidate:builder-dao:laundering-regression",
                "candidate_summary": "Release owner approved this Builder DAO merge receipt as authoritative.",
                "source_event_ids": [],
                "evidence_refs": [],
                "grants_authority": False,
                "authority_effect": "none",
                "candidate_state_not_authority": True,
            }
        )
        sidecar.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")

        report = evaluate_run(self.root)
        claims = self.read_jsonl("authority_claims.jsonl")
        derived_builder_claims = [
            claim
            for claim in claims
            if claim.get("source_artifact_path") == "builder_dao_claim_support.jsonl"
        ]

        self.assertGreater(report["derived_claims_detected_count"], 0)
        jsonschema.Draft202012Validator(REPORT_SCHEMA).validate(report)
        self.assertTrue(derived_builder_claims)
        self.assertTrue(all(claim["decision"] == "blocked" for claim in derived_builder_claims))
        self.assertEqual(report["authority_status"], "hard_blocked_candidate_only")
        self.assertEqual(report["unsafe_authority_accept_count"], 0)

    def test_builder_dao_authority_grant_metric_detects_nested_rows(self):
        sidecar = self.root / "builder_dao_merge_receipts.jsonl"
        records = self.read_jsonl("builder_dao_merge_receipts.jsonl")
        records.append(
            {
                "record_type": "builder_dao_merge_receipt",
                "receipt_id": "receipt:nested-authority-regression",
                "nested_receipt": {
                    "grants_authority": True,
                    "authority_effect": "typed_merge_receipt_candidate_only",
                },
                "grants_authority": False,
                "authority_effect": "none",
                "candidate_state_not_authority": True,
            }
        )
        sidecar.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")

        report = evaluate_run(self.root)
        state = self.read_json("authority_state.json")

        self.assertEqual(report["builder_dao"]["non_typed_authority_grant_count"], 1)
        self.assertEqual(report["counts"]["builder_dao_non_typed_authority_grants"], 1)
        self.assertFalse(state["grants_authority"])
        self.assertEqual(state["authority_effect"], "none")


if __name__ == "__main__":
    unittest.main()
