"""JSON schema contract tests for Authority-Aware Agent Workspace artifacts."""

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "schemas"

REQUIRED_SCHEMA_FILES = (
    "event-envelope.schema.json",
    "run-manifest.schema.json",
    "scenario.schema.json",
    "authority-evaluator-report.schema.json",
)

PROTOCOLS = ["raw_chat_v0", "typed_evidence_v0"]
CONTEXT_MODES = [
    "raw_transcript",
    "validated_only",
    "digest_only",
    "typed_handoff_only",
    "evidence_only",
    "poisoned_raw",
    "redacted_raw",
    "attribution_blind",
]
FIXTURE_TYPES = [
    "side_channel_approval",
    "stale_summary",
    "fake_completion",
    "channel_membership_authority",
    "missing_receipt",
    "poisoned_instruction",
    "ambiguous_ownership",
    "overbroad_delegation",
    "synthetic_authority_controls",
]
OUTCOME_FIELDS = [
    "unsafe_authority_accept_count",
    "blocked_authority_claim_count",
    "authority_control_case_count",
    "authority_valid_accept_count",
    "authority_valid_reject_count",
    "authority_invalid_accept_count",
    "authority_invalid_reject_count",
    "authority_false_accept_count",
    "authority_false_reject_count",
    "real_authority_grant_events",
    "synthetic_authority_fixture_events",
    "evidence_linked_candidate_state_rate",
    "evidence_linked_candidate_object_rate",
    "unsupported_candidate_state_count",
    "unsupported_candidate_object_count",
    "orphan_source_ref_count",
    "missing_source_ref_count",
    "authority_state_changed_by_invalid_claim",
    "raw_claims_detected_count",
    "derived_claims_detected_count",
    "report_ambiguous_authority_language_count",
]
FINDING_FIELDS = [
    "finding_id",
    "claim_id",
    "severity",
    "claim_type",
    "claim_text",
    "normalized_claim",
    "actor_id",
    "source_event_ids",
    "evidence_refs",
    "candidate_state_refs",
    "asserted_action",
    "asserted_target",
    "asserted_scope",
    "required_rule",
    "failure_reason",
    "decision",
    "human_explanation",
]


class JsonSchemaContractTests(unittest.TestCase):
    def load_schema(self, name):
        path = SCHEMAS_DIR / name
        with path.open(encoding="utf-8") as schema_file:
            return json.load(schema_file)

    def test_required_schema_files_exist(self):
        for schema_name in REQUIRED_SCHEMA_FILES:
            with self.subTest(schema_name=schema_name):
                self.assertTrue((SCHEMAS_DIR / schema_name).is_file())

    def test_every_schema_is_valid_json_object(self):
        for schema_name in REQUIRED_SCHEMA_FILES:
            with self.subTest(schema_name=schema_name):
                schema = self.load_schema(schema_name)
                self.assertIsInstance(schema, dict)
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertIn("title", schema)
                self.assertEqual(schema["type"], "object")
                self.assertIn("required", schema)
                self.assertIn("properties", schema)

    def test_event_envelope_schema_encodes_non_authority_invariants(self):
        schema = self.load_schema("event-envelope.schema.json")
        properties = schema["properties"]

        self.assertIn("source_refs", properties)
        self.assertEqual(properties["source_refs"]["items"], {"$ref": "#/$defs/source_ref"})
        source_ref = schema["$defs"]["source_ref"]
        self.assertEqual(source_ref["required"], ["ref_type", "ref_id", "relationship"])
        self.assertEqual(properties["grants_authority"], {"type": "boolean"})
        self.assertEqual(properties["authority_effect"], {"enum": ["none", "synthetic_authority_fixture"]})
        self.assertEqual(properties["candidate_state_not_authority"], {"const": True})
        conditional_text = json.dumps(schema["allOf"], sort_keys=True)
        self.assertIn("synthetic_authority_fixture", conditional_text)
        self.assertIn("authority.synthetic_grant.recorded", conditional_text)

    def test_event_schema_requires_source_refs_for_derived_events(self):
        schema = self.load_schema("event-envelope.schema.json")

        self.assertIn("allOf", schema)
        conditional_text = json.dumps(schema["allOf"], sort_keys=True)
        self.assertIn("minItems", conditional_text)
        self.assertIn("workspace.message.recorded", conditional_text)
        self.assertIn("workspace.dm.recorded", conditional_text)

    def test_run_manifest_schema_has_required_contract_fields(self):
        schema = self.load_schema("run-manifest.schema.json")
        expected_required = [
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
        ]
        self.assertEqual(schema["required"], expected_required)
        for field_name in expected_required:
            self.assertIn(field_name, schema["properties"])
        self.assertEqual(schema["properties"]["scenario_sha256"]["pattern"], "^sha256:[0-9a-f]{64}$")
        self.assertEqual(schema["properties"]["fixture_type"]["enum"], FIXTURE_TYPES)
        self.assertEqual(schema["properties"]["protocol"]["enum"], PROTOCOLS)
        self.assertEqual(schema["properties"]["context_mode"]["enum"], CONTEXT_MODES)

    def test_run_manifest_artifact_entries_require_hash_size_and_line_count(self):
        schema = self.load_schema("run-manifest.schema.json")
        artifact_schema = schema["properties"]["artifacts"]["items"]

        self.assertEqual(artifact_schema["required"], ["path", "sha256", "bytes", "jsonl_line_count"])
        self.assertEqual(artifact_schema["properties"]["sha256"]["pattern"], "^sha256:[0-9a-f]{64}$")

    def test_scenario_schema_has_async_workspace_fields(self):
        schema = self.load_schema("scenario.schema.json")
        expected_required = [
            "scenario_id",
            "title",
            "fixture_type",
            "protocol",
            "context_mode",
            "seed",
            "agents",
            "channels",
            "dm_threads",
            "tasks",
            "artifact_drafts",
            "handoffs",
            "scripted_events",
        ]
        self.assertEqual(schema["required"], expected_required)
        for field_name in expected_required:
            self.assertIn(field_name, schema["properties"])
        self.assertEqual(schema["properties"]["agents"]["minItems"], 1)
        self.assertTrue(schema["properties"]["agents"]["uniqueItems"])
        self.assertEqual(schema["properties"]["fixture_type"]["enum"], FIXTURE_TYPES)
        self.assertEqual(schema["properties"]["protocol"]["enum"], PROTOCOLS)
        self.assertEqual(schema["properties"]["context_mode"]["enum"], CONTEXT_MODES)

    def test_evaluator_report_schema_has_treatment_and_outcome_fields(self):
        schema = self.load_schema("authority-evaluator-report.schema.json")
        required = schema["required"]
        for field_name in [
            "scenario_id",
            "scenario_sha256",
            "fixture_type",
            "protocol",
            "context_mode",
            "seed",
            "runner_version",
            "authority_status",
            "counts",
            "findings",
        ] + OUTCOME_FIELDS:
            with self.subTest(field_name=field_name):
                self.assertIn(field_name, required)
                self.assertIn(field_name, schema["properties"])
        self.assertEqual(schema["properties"]["real_authority_grant_events"], {"const": 0})
        self.assertEqual(schema["properties"]["synthetic_authority_fixture_events"], {"type": "integer", "minimum": 0})
        self.assertEqual(schema["properties"]["authority_state_changed_by_invalid_claim"], {"const": False})

    def test_evaluator_finding_schema_matches_plan_minimum(self):
        schema = self.load_schema("authority-evaluator-report.schema.json")
        finding = schema["$defs"]["finding"]

        self.assertEqual(finding["required"], FINDING_FIELDS)
        self.assertEqual(finding["properties"]["severity"]["enum"], ["low", "medium", "high", "authority_critical"])
        self.assertEqual(
            finding["properties"]["claim_type"]["enum"],
            [
                "approval_claim",
                "authorization_claim",
                "completion_claim",
                "blocker_closure_claim",
                "delegation_claim",
                "receipt_sufficiency_claim",
                "poisoned_instruction_claim",
                "role_grant_claim",
                "scope_claim",
            ],
        )
        self.assertEqual(
            finding["properties"]["decision"]["enum"],
            ["blocked", "accepted_candidate_only", "needs_human_review"],
        )
        self.assertIn("source_event_ids", finding["properties"])
        self.assertEqual(finding["properties"]["source_event_ids"]["minItems"], 1)

    def test_evaluator_report_schema_tightens_synthetic_control_findings(self):
        schema = self.load_schema("authority-evaluator-report.schema.json")
        control_finding = schema["$defs"]["authority_control_finding"]

        self.assertEqual(schema["properties"]["authority_control_findings"]["items"], {"$ref": "#/$defs/authority_control_finding"})
        self.assertFalse(control_finding["additionalProperties"])
        for field_name in [
            "case_id",
            "grant_id",
            "event_id",
            "actor_id",
            "action",
            "target",
            "scope",
            "decision",
            "oracle_authority_valid",
            "oracle_match",
            "formal_grant_present",
            "channel_member",
            "failure_reason",
            "human_explanation",
            "synthetic_sandbox_only",
        ]:
            with self.subTest(field_name=field_name):
                self.assertIn(field_name, control_finding["required"])
                self.assertIn(field_name, control_finding["properties"])
        self.assertEqual(control_finding["properties"]["decision"]["enum"], ["accepted", "rejected"])
        self.assertEqual(control_finding["properties"]["synthetic_sandbox_only"], {"const": True})

    def test_schema_readme_mentions_no_authority_invariant(self):
        readme_text = (SCHEMAS_DIR / "README.md").read_text(encoding="utf-8").lower()
        self.assertIn("no-authority invariant", readme_text)
        self.assertIn("grants_authority false", readme_text)
        self.assertIn("authority_effect none", readme_text)
        self.assertIn("authority_state_changed_by_invalid_claim", readme_text)
        self.assertIn("source event ids", readme_text)


if __name__ == "__main__":
    unittest.main()
