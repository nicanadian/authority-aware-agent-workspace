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

        for relative_path in ["run_manifest.json", *INITIAL_ARTIFACTS]:
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
        self.assertEqual([entry["path"] for entry in manifest["artifacts"]], INITIAL_ARTIFACTS)

        # Task 6 explicitly excludes run_manifest.json from manifest artifacts to avoid self-hash recursion.
        self.assertNotIn("run_manifest.json", [entry["path"] for entry in manifest["artifacts"]])
        for entry in manifest["artifacts"]:
            contents = (self.root / entry["path"]).read_bytes()
            self.assertEqual(entry["sha256"], "sha256:" + hashlib.sha256(contents).hexdigest())
            self.assertEqual(entry["bytes"], len(contents))
            self.assertEqual(entry["jsonl_line_count"], len(contents.decode("utf-8").splitlines()))

    def test_jsonl_artifacts_parse_line_by_line(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        self.assertEqual(len(self.read_jsonl("workspace_events.jsonl")), 4)
        self.assertEqual(len(self.read_jsonl("channel_messages.jsonl")), 2)
        self.assertEqual(len(self.read_jsonl("dm_messages.jsonl")), 2)
        self.assertEqual(len(self.read_jsonl("context_exposure.jsonl")), 1)

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

    def test_context_exposure_records_visibility_and_no_model_call_context(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        event_ids = [event["event_id"] for event in self.read_jsonl("workspace_events.jsonl")]
        exposure = self.read_jsonl("context_exposure.jsonl")[0]

        self.assertEqual(exposure["actor_id"], "system:runner")
        self.assertEqual(exposure["protocol"], "raw_chat_v0")
        self.assertEqual(exposure["context_mode"], "raw_transcript")
        self.assertEqual(exposure["visible_event_ids"], event_ids)
        self.assertEqual(exposure["source_event_ids"], event_ids)
        self.assertEqual(exposure["hidden_canonical_state_refs"], [])
        self.assertEqual(exposure["poison_markers_visible"], [])
        self.assertGreater(exposure["context_bytes"], 0)
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
        for relative_path in ["run_manifest.json", *INITIAL_ARTIFACTS]:
            with self.subTest(relative_path=relative_path):
                self.assertEqual(
                    (first_root / relative_path).read_bytes(),
                    (second_root / relative_path).read_bytes(),
                )


if __name__ == "__main__":
    unittest.main()
