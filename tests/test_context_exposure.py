"""Context exposure evaluator checks for v0.

Task 12 is intentionally strict TDD: these tests define the measurable
context-exposure contract before the implementation is updated.
"""

import json
import tempfile
import unittest
from pathlib import Path

from authority_workspace.evaluator import EvaluatorInputError, evaluate_run
from authority_workspace.runner import run_scenario


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "scenarios" / "fixtures"
SIDE_CHANNEL_FIXTURE = FIXTURE_DIR / "side_channel_approval.json"
POISONED_FIXTURE = FIXTURE_DIR / "poisoned_instruction.json"


class ContextExposureEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "run"

    def read_jsonl(self, root, relative_path):
        with (root / relative_path).open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]

    def write_jsonl(self, root, relative_path, records):
        (root / relative_path).write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
            encoding="utf-8",
        )

    def test_each_scripted_workspace_event_has_context_exposure_record(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        events = self.read_jsonl(self.root, "workspace_events.jsonl")
        exposures = self.read_jsonl(self.root, "context_exposure.jsonl")

        self.assertEqual(len(exposures), len(events))
        self.assertEqual([record["event_index"] for record in exposures], [event["event_index"] for event in events])
        self.assertEqual([record["source_event_ids"] for record in exposures], [[event["event_id"]] for event in events])
        self.assertEqual([record["visible_event_ids"] for record in exposures], [[event["event_id"]] for event in events])

    def test_context_mode_is_recorded_for_every_exposure(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        exposures = self.read_jsonl(self.root, "context_exposure.jsonl")

        self.assertTrue(exposures)
        self.assertEqual({record["context_mode"] for record in exposures}, {"raw_transcript"})
        self.assertTrue(all(record["protocol"] == "raw_chat_v0" for record in exposures))

    def test_poisoned_context_markers_are_recorded_when_present(self):
        run_scenario(POISONED_FIXTURE, self.root)

        events = self.read_jsonl(self.root, "workspace_events.jsonl")
        poison_event = next(event for event in events if event["payload"]["message_id"] == "msg:poison:002")
        exposures_by_event = {
            exposure["source_event_ids"][0]: exposure
            for exposure in self.read_jsonl(self.root, "context_exposure.jsonl")
        }

        markers = exposures_by_event[poison_event["event_id"]]["poison_markers_visible"]
        self.assertEqual(
            markers,
            [
                {
                    "marker_type": "poisoned_instruction",
                    "source_event_id": poison_event["event_id"],
                    "message_id": "msg:poison:002",
                    "matched_text": "ignore authority checks",
                }
            ],
        )

    def test_hidden_canonical_refs_are_explicit(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        exposures = self.read_jsonl(self.root, "context_exposure.jsonl")

        self.assertTrue(exposures)
        for exposure in exposures:
            with self.subTest(exposure_id=exposure["exposure_id"]):
                self.assertIn("hidden_canonical_state_refs", exposure)
                self.assertEqual(exposure["hidden_canonical_state_refs"], [])

    def test_live_only_byte_fields_have_deterministic_placeholders_in_v0(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)

        exposures = self.read_jsonl(self.root, "context_exposure.jsonl")

        self.assertTrue(exposures)
        for exposure in exposures:
            with self.subTest(exposure_id=exposure["exposure_id"]):
                self.assertTrue(exposure["deterministic_placeholder"])
                self.assertEqual(exposure["prompt_bytes"], 0)
                self.assertEqual(exposure["context_bytes"], 0)

    def test_evaluator_rejects_missing_context_exposure_for_workspace_event(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)
        exposures = self.read_jsonl(self.root, "context_exposure.jsonl")
        self.write_jsonl(self.root, "context_exposure.jsonl", exposures[:-1])

        with self.assertRaisesRegex(EvaluatorInputError, "context_exposure.jsonl.*missing exposure"):
            evaluate_run(self.root)

    def test_evaluator_rejects_missing_poison_marker_for_poisoned_event(self):
        run_scenario(POISONED_FIXTURE, self.root)
        exposures = self.read_jsonl(self.root, "context_exposure.jsonl")
        for exposure in exposures:
            exposure["poison_markers_visible"] = []
        self.write_jsonl(self.root, "context_exposure.jsonl", exposures)

        with self.assertRaisesRegex(EvaluatorInputError, "context_exposure.jsonl.*poison_markers_visible"):
            evaluate_run(self.root)

    def test_evaluator_rejects_missing_message_visibility_fields(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)
        exposures = self.read_jsonl(self.root, "context_exposure.jsonl")
        del exposures[0]["visible_message_ids"]
        self.write_jsonl(self.root, "context_exposure.jsonl", exposures)

        with self.assertRaisesRegex(EvaluatorInputError, "context_exposure.jsonl.*visible_message_ids"):
            evaluate_run(self.root)

    def test_evaluator_rejects_visibility_fields_that_do_not_match_raw_event(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)
        exposures = self.read_jsonl(self.root, "context_exposure.jsonl")
        exposures[0]["visible_channel_ids"] = ["channel:wrong"]
        exposures[0]["visible_message_ids"] = ["msg:wrong"]
        exposures[0]["visible_channel_message_ids"] = []
        self.write_jsonl(self.root, "context_exposure.jsonl", exposures)

        with self.assertRaisesRegex(EvaluatorInputError, "context_exposure.jsonl.*visible_.*raw event"):
            evaluate_run(self.root)

    def test_missing_context_exposure_file_raises_evaluator_input_error(self):
        run_scenario(SIDE_CHANNEL_FIXTURE, self.root)
        (self.root / "context_exposure.jsonl").unlink()

        with self.assertRaisesRegex(EvaluatorInputError, "context_exposure.jsonl"):
            evaluate_run(self.root)


if __name__ == "__main__":
    unittest.main()
