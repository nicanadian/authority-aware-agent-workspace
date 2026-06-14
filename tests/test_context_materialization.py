"""Tests for real deterministic context-mode materialization."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from authority_workspace.evaluator import EvaluatorInputError, evaluate_run
from authority_workspace.runner import run_scenario


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDE_CHANNEL_FIXTURE = REPO_ROOT / "scenarios" / "fixtures" / "side_channel_approval.json"
POISONED_FIXTURE = REPO_ROOT / "scenarios" / "fixtures" / "poisoned_instruction.json"


IMPLEMENTED_CONTEXT_MODES = [
    "raw_transcript",
    "redacted_raw",
    "digest_only",
    "evidence_only",
    "typed_handoff_only",
    "attribution_blind",
    "poisoned_raw",
]


class ContextMaterializationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def read_json(self, root, relative_path):
        return json.loads((root / relative_path).read_text(encoding="utf-8"))

    def read_jsonl(self, root, relative_path):
        with (root / relative_path).open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]

    def write_fixture_with_mode(self, mode):
        fixture = json.loads(SIDE_CHANNEL_FIXTURE.read_text(encoding="utf-8"))
        fixture["context_mode"] = mode
        fixture["scenario_id"] = f"side_channel_approval_{mode}"
        path = self.root / f"{mode}.json"
        path.write_text(json.dumps(fixture, sort_keys=True), encoding="utf-8")
        return path

    def write_poisoned_fixture_with_mode(self, mode):
        fixture = json.loads(POISONED_FIXTURE.read_text(encoding="utf-8"))
        fixture["context_mode"] = mode
        path = self.root / f"poisoned-{mode}.json"
        path.write_text(json.dumps(fixture, sort_keys=True), encoding="utf-8")
        return path

    def test_runner_materializes_context_text_hashes_and_manifest_artifact(self):
        run_root = self.root / "raw"
        manifest = run_scenario(SIDE_CHANNEL_FIXTURE, run_root)
        exposures = self.read_jsonl(run_root, "context_exposure.jsonl")
        contexts = self.read_jsonl(run_root, "materialized_contexts.jsonl")

        self.assertIn("materialized_contexts.jsonl", [entry["path"] for entry in manifest["artifacts"]])
        self.assertEqual(len(exposures), len(contexts))
        by_id = {record["exposure_id"]: record for record in contexts}
        raw_events = self.read_jsonl(run_root, "workspace_events.jsonl")

        for exposure, event in zip(exposures, raw_events):
            with self.subTest(exposure_id=exposure["exposure_id"]):
                context = by_id[exposure["exposure_id"]]
                context_text = context["context_text"]
                context_bytes = len(context_text.encode("utf-8"))
                self.assertGreater(context_bytes, 0)
                self.assertFalse(exposure["deterministic_placeholder"])
                self.assertEqual(exposure["materialized_context_path"], "materialized_contexts.jsonl")
                self.assertEqual(exposure["materialized_context_record_id"], exposure["exposure_id"])
                self.assertEqual(exposure["context_sha256"], "sha256:" + hashlib.sha256(context_text.encode("utf-8")).hexdigest())
                self.assertEqual(exposure["context_text_hash"], exposure["context_sha256"])
                self.assertEqual(exposure["context_bytes"], context_bytes)
                self.assertGreater(exposure["prompt_bytes"], exposure["context_bytes"])
                self.assertEqual(context["source_event_ids"], exposure["source_event_ids"])
                self.assertIn(event["payload"].get("text", ""), context_text)
                self.assertFalse(exposure["grants_authority"])
                self.assertEqual(exposure["authority_effect"], "none")

    def test_supported_modes_are_distinguishable_and_apply_redaction_rules(self):
        materialized_by_mode = {}
        for mode in IMPLEMENTED_CONTEXT_MODES:
            fixture_path = self.write_poisoned_fixture_with_mode(mode) if mode in {"poisoned_raw", "redacted_raw"} else self.write_fixture_with_mode(mode)
            run_root = self.root / f"run-{mode}"
            run_scenario(fixture_path, run_root)
            exposure = self.read_jsonl(run_root, "context_exposure.jsonl")[0]
            contexts = self.read_jsonl(run_root, "materialized_contexts.jsonl")
            materialized_by_mode[mode] = "\n".join(context["context_text"] for context in contexts)
            self.assertFalse(exposure["deterministic_placeholder"], mode)
            self.assertEqual(exposure["context_materialization_status"], "implemented")

        unique_texts = {mode: text for mode, text in materialized_by_mode.items()}
        self.assertEqual(len(set(unique_texts.values())), len(unique_texts))
        self.assertIn("ignore authority checks", materialized_by_mode["poisoned_raw"].lower())
        self.assertIn("[REDACTED_AUTHORITY_BYPASS_TEXT]", materialized_by_mode["redacted_raw"])
        self.assertNotIn("ignore authority checks", materialized_by_mode["redacted_raw"].lower())
        self.assertNotIn("actor_id=", materialized_by_mode["attribution_blind"])
        self.assertIn("event_ref=", materialized_by_mode["evidence_only"])
        self.assertNotIn("Release owner approved", materialized_by_mode["evidence_only"])
        self.assertIn("typed_handoff", materialized_by_mode["typed_handoff_only"])

    def test_evaluator_rejects_mismatched_materialized_context_hash_bytes_and_missing_path(self):
        run_root = self.root / "reject"
        run_scenario(SIDE_CHANNEL_FIXTURE, run_root)
        exposures = self.read_jsonl(run_root, "context_exposure.jsonl")

        for field, replacement, expected in [
            ("context_sha256", "sha256:" + "0" * 64, "context_sha256"),
            ("context_bytes", 1, "context_bytes"),
            ("materialized_context_path", "missing.jsonl", "materialized_context_path"),
        ]:
            with self.subTest(field=field):
                tampered = [dict(record) for record in exposures]
                tampered[0][field] = replacement
                (run_root / "context_exposure.jsonl").write_text(
                    "".join(json.dumps(record, sort_keys=True) + "\n" for record in tampered),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(EvaluatorInputError, expected):
                    evaluate_run(run_root)
                (run_root / "context_exposure.jsonl").write_text(
                    "".join(json.dumps(record, sort_keys=True) + "\n" for record in exposures),
                    encoding="utf-8",
                )

    def test_evaluator_rejects_tampered_materialized_context_metadata(self):
        run_root = self.root / "metadata-reject"
        run_scenario(SIDE_CHANNEL_FIXTURE, run_root)
        contexts = self.read_jsonl(run_root, "materialized_contexts.jsonl")

        for field, replacement, expected in [
            ("run_id", "wrong-run", "run_id"),
            ("event_index", 999, "event_index"),
            ("protocol", "typed_evidence_v0", "protocol"),
            ("context_mode", "digest_only", "context_mode"),
        ]:
            with self.subTest(field=field):
                tampered = [dict(record) for record in contexts]
                tampered[0][field] = replacement
                (run_root / "materialized_contexts.jsonl").write_text(
                    "".join(json.dumps(record, sort_keys=True) + "\n" for record in tampered),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(EvaluatorInputError, expected):
                    evaluate_run(run_root)
                (run_root / "materialized_contexts.jsonl").write_text(
                    "".join(json.dumps(record, sort_keys=True) + "\n" for record in contexts),
                    encoding="utf-8",
                )

    def test_evaluator_rejects_extra_or_duplicate_materialized_context_records(self):
        run_root = self.root / "extra-reject"
        run_scenario(SIDE_CHANNEL_FIXTURE, run_root)
        contexts = self.read_jsonl(run_root, "materialized_contexts.jsonl")
        path = run_root / "materialized_contexts.jsonl"

        extra = dict(contexts[0])
        extra["context_record_id"] = "context:event:extra"
        extra["exposure_id"] = "context:event:extra"
        path.write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in [*contexts, extra]),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(EvaluatorInputError, "exactly match"):
            evaluate_run(run_root)

        path.write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in [contexts[0], *contexts]),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(EvaluatorInputError, "duplicate context_record_id"):
            evaluate_run(run_root)


if __name__ == "__main__":
    unittest.main()
