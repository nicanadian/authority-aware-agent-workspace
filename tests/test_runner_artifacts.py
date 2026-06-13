"""Minimal runner artifact tests."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from authority_workspace.events import REQUIRED_FIELDS, validate_event
from authority_workspace.runner import run_scenario


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDE_CHANNEL_FIXTURE = REPO_ROOT / "scenarios" / "fixtures" / "side_channel_approval.json"
INITIAL_ARTIFACTS = [
    "workspace_events.jsonl",
    "channel_messages.jsonl",
    "dm_messages.jsonl",
    "context_exposure.jsonl",
]
EVALUATOR_ARTIFACTS = [
    "authority_claims.jsonl",
    "authority_state.json",
    "authority_evaluator_report.json",
    "evidence_manifest.json",
]
CANDIDATE_ARTIFACTS = [
    "tasks.jsonl",
    "artifact_patches.jsonl",
    "candidate_state.jsonl",
    "candidate_state_reviews.jsonl",
]
ALL_ARTIFACTS = [*INITIAL_ARTIFACTS, *CANDIDATE_ARTIFACTS, *EVALUATOR_ARTIFACTS]


class MinimalRunnerArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "run"

    def read_json(self, relative_path):
        return json.loads((self.root / relative_path).read_text(encoding="utf-8"))

    def read_jsonl(self, relative_path):
        records = []
        with (self.root / relative_path).open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                with self.subTest(path=relative_path, line=line_number):
                    self.assertTrue(line.endswith("\n"))
                    records.append(json.loads(line))
        return records

    def test_runner_writes_initial_artifacts_and_manifest(self):
        manifest = run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        for relative_path in ["run_manifest.json", *ALL_ARTIFACTS]:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((self.root / relative_path).is_file())

        self.assertEqual(manifest, self.read_json("run_manifest.json"))
        self.assertEqual(manifest["schema_version"], "aaaw.run_manifest.v1")
        self.assertEqual(manifest["run_id"], "deterministic-run")
        self.assertEqual(manifest["scenario_id"], "side_channel_approval")
        self.assertEqual(
            manifest["scenario_sha256"],
            "sha256:" + hashlib.sha256(SIDE_CHANNEL_FIXTURE.read_bytes()).hexdigest(),
        )
        self.assertEqual(manifest["fixture_type"], "side_channel_approval")
        self.assertEqual(manifest["protocol"], "raw_chat_v0")
        self.assertEqual(manifest["context_mode"], "raw_transcript")
        self.assertEqual(manifest["seed"], 4001)
        self.assertEqual(manifest["artifact_schema_version"], "aaaw.artifacts.v1")
        self.assertTrue(manifest["runner_version"])
        self.assertEqual([entry["path"] for entry in manifest["artifacts"]], ALL_ARTIFACTS)

        # Task 6 explicitly excludes run_manifest.json from manifest artifacts to avoid self-hash recursion.
        self.assertNotIn("run_manifest.json", [entry["path"] for entry in manifest["artifacts"]])
        for entry in manifest["artifacts"]:
            contents = (self.root / entry["path"]).read_bytes()
            self.assertEqual(entry["sha256"], "sha256:" + hashlib.sha256(contents).hexdigest())
            self.assertEqual(entry["bytes"], len(contents))
            expected_line_count = len(contents.decode("utf-8").splitlines()) if entry["path"].endswith(".jsonl") else 0
            self.assertEqual(entry["jsonl_line_count"], expected_line_count)

    def test_jsonl_artifacts_parse_line_by_line(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        self.assertEqual(len(self.read_jsonl("workspace_events.jsonl")), 4)
        self.assertEqual(len(self.read_jsonl("channel_messages.jsonl")), 2)
        self.assertEqual(len(self.read_jsonl("dm_messages.jsonl")), 2)
        self.assertEqual(len(self.read_jsonl("context_exposure.jsonl")), 4)
        self.assertEqual(len(self.read_jsonl("tasks.jsonl")), 1)
        self.assertEqual(len(self.read_jsonl("artifact_patches.jsonl")), 1)
        self.assertEqual(len(self.read_jsonl("candidate_state.jsonl")), 2)
        self.assertEqual(len(self.read_jsonl("candidate_state_reviews.jsonl")), 2)
        self.assertEqual(len(self.read_jsonl("authority_claims.jsonl")), 2)

    def test_runner_evaluator_report_metrics_match_side_channel_fixture(self):
        manifest = run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        report = self.read_json("authority_evaluator_report.json")
        claims = self.read_jsonl("authority_claims.jsonl")
        self.assertEqual(report["scenario_id"], "side_channel_approval")
        self.assertEqual(report["fixture_type"], "side_channel_approval")
        self.assertEqual(report["protocol"], "raw_chat_v0")
        self.assertEqual(report["context_mode"], "raw_transcript")
        self.assertEqual(report["runner_version"], manifest["runner_version"])
        self.assertEqual(report["counts"], {
            "raw_events_scored": 4,
            "raw_authority_claims": 2,
            "blocked_findings": 2,
            "candidate_objects": 6,
            "unsupported_candidate_objects": 3,
            "evidence_linked_candidate_objects": 3,
            "candidate_state_objects": 4,
            "unsupported_candidate_state_objects": 2,
            "evidence_linked_candidate_state_objects": 2,
        })
        self.assertEqual(report["raw_claims_detected_count"], 2)
        self.assertEqual(report["blocked_authority_claim_count"], 2)
        self.assertEqual(report["unsupported_candidate_state_count"], 3)
        self.assertEqual(report["unsupported_candidate_object_count"], 3)
        self.assertEqual(report["evidence_linked_candidate_state_rate"], 0.5)
        self.assertEqual(report["evidence_linked_candidate_object_rate"], 0.5)
        self.assertEqual(len(report["findings"]), 2)
        self.assertEqual(len(claims), 2)
        self.assertTrue(all(claim["claim_type"] == "approval_claim" for claim in claims))
        self.assertTrue(all(finding["decision"] == "blocked" for finding in report["findings"]))

    def test_no_invalid_claim_mutates_authority_state(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        state = self.read_json("authority_state.json")
        report = self.read_json("authority_evaluator_report.json")
        self.assertEqual(state["authority_status"], "hard_blocked_candidate_only")
        self.assertFalse(state["grants_authority"])
        self.assertEqual(state["authority_effect"], "none")
        self.assertTrue(state["candidate_state_not_authority"])
        self.assertFalse(state["authority_state_changed_by_invalid_claim"])
        self.assertEqual(state["unsafe_authority_accept_count"], 0)
        self.assertEqual(state["real_authority_grant_events"], 0)
        self.assertEqual(state["synthetic_authority_fixture_events"], 0)
        self.assertEqual(state["blocked_authority_claim_count"], 2)
        self.assertFalse(report["authority_state_changed_by_invalid_claim"])
        self.assertEqual(report["unsafe_authority_accept_count"], 0)

    def test_evidence_manifest_includes_evaluator_outputs_as_non_authority(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        evidence_manifest = self.read_json("evidence_manifest.json")
        self.assertEqual(evidence_manifest["authority_status"], "hard_blocked_candidate_only")
        self.assertEqual(evidence_manifest["evaluator_outputs"], EVALUATOR_ARTIFACTS)
        self.assertEqual(
            [entry["path"] for entry in evidence_manifest["artifacts"]],
            [*INITIAL_ARTIFACTS, *CANDIDATE_ARTIFACTS, "authority_claims.jsonl", "authority_state.json", "authority_evaluator_report.json"],
        )
        for entry in evidence_manifest["artifacts"]:
            self.assertFalse(entry["grants_authority"])
            self.assertEqual(entry["authority_effect"], "none")
            self.assertTrue(entry["candidate_state_not_authority"])

    def test_workspace_events_are_full_non_authority_envelopes(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        events = self.read_jsonl("workspace_events.jsonl")
        self.assertEqual([event["event_index"] for event in events], [0, 1, 2, 3])
        self.assertEqual([event["event_type"] for event in events], [
            "workspace.message.recorded",
            "workspace.message.recorded",
            "workspace.dm.recorded",
            "workspace.dm.recorded",
        ])
        for event in events:
            with self.subTest(event_index=event["event_index"]):
                self.assertEqual(set(event), set(REQUIRED_FIELDS))
                self.assertIs(validate_event(event), event)
                self.assertFalse(event["grants_authority"])
                self.assertEqual(event["authority_effect"], "none")
                self.assertTrue(event["candidate_state_not_authority"])

    def test_projection_records_link_back_to_workspace_events(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        events = self.read_jsonl("workspace_events.jsonl")
        event_ids = {event["event_id"] for event in events}
        message_to_event = {}
        for event in events:
            payload = event["payload"]
            source_id = payload.get("channel_id") or payload.get("thread_id")
            message_to_event[(source_id, payload["message_id"])] = event["event_id"]

        for relative_path in ["channel_messages.jsonl", "dm_messages.jsonl"]:
            for record in self.read_jsonl(relative_path):
                with self.subTest(relative_path=relative_path, message_id=record["message_id"]):
                    source_id = record.get("channel_id") or record.get("thread_id")
                    self.assertEqual(record["source_event_id"], message_to_event[(source_id, record["message_id"])])
                    self.assertEqual(record["source_event_ids"], [record["source_event_id"]])
                    self.assertIn(record["source_event_id"], event_ids)

    def test_candidate_outputs_are_non_authoritative_and_evidence_linked_or_unsupported(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        event_ids = {event["event_id"] for event in self.read_jsonl("workspace_events.jsonl")}
        candidate_records = []
        for relative_path in CANDIDATE_ARTIFACTS:
            for record in self.read_jsonl(relative_path):
                candidate_records.append((relative_path, record))

        self.assertEqual(len(candidate_records), 6)
        unsupported = []
        linked_candidate_state = []
        required_candidate_fields = {
            "candidate_id",
            "candidate_type",
            "source_event_ids",
            "evidence_refs",
            "extraction_method",
            "review_status",
            "authority_effect",
            "candidate_state_not_authority",
        }
        task_source_event_ids = []
        for relative_path, record in candidate_records:
            with self.subTest(relative_path=relative_path, candidate_id=record.get("candidate_id") or record.get("task_id") or record.get("patch_id")):
                self.assertTrue(required_candidate_fields.issubset(record), sorted(set(required_candidate_fields) - set(record)))
                self.assertFalse(record["grants_authority"])
                self.assertEqual(record["authority_effect"], "none")
                self.assertTrue(record["candidate_state_not_authority"])
                self.assertNotIn(record.get("authority_status"), {"approved", "authorized", "granted"})

                if record.get("review_status") == "unsupported":
                    unsupported.append(record)
                    self.assertEqual(record["source_event_ids"], [])
                    self.assertEqual(record["evidence_refs"], [])
                    self.assertTrue(record["unsupported_reason"])
                else:
                    self.assertGreaterEqual(len(record["source_event_ids"]), 1)
                    self.assertTrue(set(record["source_event_ids"]).issubset(event_ids))
                    self.assertTrue(record["evidence_refs"])
                    if record.get("candidate_id") == "candidate:task:task:release-note":
                        task_source_event_ids = record["source_event_ids"]
                    if relative_path in {"candidate_state.jsonl", "candidate_state_reviews.jsonl"}:
                        linked_candidate_state.append(record)

        source_messages = {
            event["event_id"]: event["payload"].get("message_id")
            for event in self.read_jsonl("workspace_events.jsonl")
        }
        self.assertEqual([source_messages[event_id] for event_id in task_source_event_ids], ["msg:release:001"])
        self.assertEqual(len(unsupported), 3)
        self.assertEqual(len(linked_candidate_state), 2)

    def test_candidate_state_does_not_mutate_authority_state(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        authority_state = self.read_json("authority_state.json")
        candidate_state = self.read_jsonl("candidate_state.jsonl")

        self.assertTrue(candidate_state)
        self.assertEqual(authority_state["authority_status"], "hard_blocked_candidate_only")
        self.assertFalse(authority_state["grants_authority"])
        self.assertEqual(authority_state["authority_effect"], "none")
        self.assertEqual(authority_state["unsafe_authority_accept_count"], 0)
        for record in candidate_state:
            with self.subTest(candidate_id=record["candidate_id"]):
                self.assertEqual(record["state_scope"], "candidate")
                self.assertFalse(record["mutates_authority_state"])
                self.assertNotEqual(record.get("state_scope"), "authority")

    def test_unmatched_task_candidate_is_marked_unsupported_not_evidence_linked(self):
        scenario = json.loads(SIDE_CHANNEL_FIXTURE.read_text(encoding="utf-8"))
        scenario["tasks"][0]["title"] = "Opaque unmatched work item"
        unmatched_fixture = self.root / "unmatched_task.json"
        unmatched_fixture.parent.mkdir(parents=True, exist_ok=True)
        unmatched_fixture.write_text(json.dumps(scenario, sort_keys=True), encoding="utf-8")

        run_scenario(unmatched_fixture, self.root / "unmatched-run")
        candidate_tasks = self.read_jsonl_from(self.root / "unmatched-run", "tasks.jsonl")
        candidate_reviews = self.read_jsonl_from(self.root / "unmatched-run", "candidate_state_reviews.jsonl")
        report = json.loads((self.root / "unmatched-run" / "authority_evaluator_report.json").read_text(encoding="utf-8"))

        task_record = candidate_tasks[0]
        review_record = next(record for record in candidate_reviews if record["reviewed_candidate_id"] == task_record["candidate_id"])
        for record in [task_record, review_record]:
            self.assertEqual(record["review_status"], "unsupported")
            self.assertEqual(record["source_event_ids"], [])
            self.assertEqual(record["evidence_refs"], [])
        self.assertEqual(report["unsupported_candidate_object_count"], 6)
        self.assertEqual(report["evidence_linked_candidate_object_rate"], 0)

    def read_jsonl_from(self, root, relative_path):
        with (root / relative_path).open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]

    def test_context_exposure_records_visibility_and_no_model_call_context(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        event_ids = [event["event_id"] for event in self.read_jsonl("workspace_events.jsonl")]
        exposure = self.read_jsonl("context_exposure.jsonl")[0]

        self.assertEqual(exposure["actor_id"], "system:runner")
        self.assertEqual(exposure["protocol"], "raw_chat_v0")
        self.assertEqual(exposure["context_mode"], "raw_transcript")
        self.assertEqual(exposure["visible_event_ids"], [event_ids[0]])
        self.assertEqual(exposure["source_event_ids"], [event_ids[0]])
        self.assertEqual(exposure["hidden_canonical_state_refs"], [])
        self.assertEqual(exposure["poison_markers_visible"], [])
        self.assertEqual(exposure["prompt_bytes"], 0)
        self.assertEqual(exposure["context_bytes"], 0)
        self.assertTrue(exposure["deterministic_placeholder"])
        self.assertFalse(exposure["grants_authority"])
        self.assertEqual(exposure["authority_effect"], "none")
        self.assertTrue(exposure["candidate_state_not_authority"])

    def test_repeated_deterministic_runs_are_byte_identical(self):
        first_root = self.root / "first"
        second_root = self.root / "second"

        first_manifest = run_scenario(SIDE_CHANNEL_FIXTURE, first_root)
        second_manifest = run_scenario(SIDE_CHANNEL_FIXTURE, second_root)

        self.assertEqual(first_manifest, second_manifest)
        for relative_path in ["run_manifest.json", *ALL_ARTIFACTS]:
            with self.subTest(relative_path=relative_path):
                self.assertEqual(
                    (first_root / relative_path).read_bytes(),
                    (second_root / relative_path).read_bytes(),
                )


if __name__ == "__main__":
    unittest.main()
