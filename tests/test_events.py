"""Canonical event envelope tests."""

import math
import unittest

from authority_workspace.events import (
    SCHEMA_VERSION,
    EventValidationError,
    create_event,
    validate_event,
)


class CanonicalEventEnvelopeTests(unittest.TestCase):
    def make_event(self, **overrides):
        values = {
            "run_id": "run-001",
            "event_index": 0,
            "event_type": "workspace.message.recorded",
            "actor_id": "agent:001",
            "payload": {"message": "hello"},
            "source_refs": [
                {
                    "ref_type": "message",
                    "ref_id": "workspace://messages/1",
                    "relationship": "derived_from",
                }
            ],
        }
        values.update(overrides)
        return create_event(**values)

    def test_all_required_fields_present(self):
        event = self.make_event()

        self.assertEqual(
            set(event),
            {
                "event_id",
                "schema_version",
                "run_id",
                "event_index",
                "event_type",
                "actor_id",
                "payload",
                "source_refs",
                "grants_authority",
                "authority_effect",
                "candidate_state_not_authority",
            },
        )
        self.assertEqual(event["schema_version"], SCHEMA_VERSION)
        self.assertFalse(event["grants_authority"])
        self.assertEqual(event["authority_effect"], "none")
        self.assertTrue(event["candidate_state_not_authority"])
        self.assertTrue(event["event_id"].startswith("aaaw-v1-"))

    def test_event_index_is_zero_based(self):
        self.assertEqual(self.make_event(event_index=0)["event_index"], 0)
        with self.assertRaises(EventValidationError):
            self.make_event(event_index=-1)

    def test_event_ids_deterministic_for_identical_canonical_input(self):
        first = self.make_event()
        second = self.make_event()

        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(first, second)

    def test_nested_dict_ordering_stable(self):
        first = self.make_event(payload={"outer": {"b": 2, "a": 1}, "z": 0})
        second = self.make_event(payload={"z": 0, "outer": {"a": 1, "b": 2}})

        self.assertEqual(first["event_id"], second["event_id"])

    def test_unicode_payload_stable(self):
        first = self.make_event(payload={"text": "café ☕ 你好", "emoji": "🚀"})
        second = self.make_event(payload={"emoji": "🚀", "text": "café ☕ 你好"})

        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(first["payload"]["text"], "café ☕ 你好")

    def test_list_ordering_preserved(self):
        first = self.make_event(payload={"items": ["a", "b"]})
        second = self.make_event(payload={"items": ["b", "a"]})

        self.assertNotEqual(first["event_id"], second["event_id"])

    def test_non_json_payload_rejected(self):
        with self.assertRaises(EventValidationError):
            self.make_event(payload={"not_json": {"set members"}})

    def test_nan_and_infinity_rejected(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(EventValidationError):
                    self.make_event(payload={"value": value})

    def test_unknown_event_types_rejected(self):
        with self.assertRaises(EventValidationError):
            self.make_event(event_type="workspace.message.deleted")

    def test_v0_rejects_grants_authority_true(self):
        event = self.make_event()
        event["grants_authority"] = True

        with self.assertRaises(EventValidationError):
            validate_event(event)

    def test_v0_rejects_authority_effect_not_none(self):
        event = self.make_event()
        event["authority_effect"] = "granted"

        with self.assertRaises(EventValidationError):
            validate_event(event)

    def test_ambiguous_authority_like_event_names_rejected_in_non_authority_namespaces(self):
        forbidden_names = [
            "workspace.release.approved",
            "workspace.deployment.authorized",
            "workspace.payment.ready",
            "workspace.blocker.closed",
            "workspace.task.approved",
            "extraction.authorized.recorded",
        ]

        for event_type in forbidden_names:
            with self.subTest(event_type=event_type):
                event = self.make_event()
                event["event_type"] = event_type
                with self.assertRaises(EventValidationError):
                    validate_event(event)

    def test_validation_rejects_missing_required_field(self):
        event = self.make_event()
        del event["actor_id"]

        with self.assertRaises(EventValidationError):
            validate_event(event)

    def test_actor_id_must_be_normalized(self):
        invalid_actor_ids = ["agent-001", "founder", "agent:", "robot:001"]

        for actor_id in invalid_actor_ids:
            with self.subTest(actor_id=actor_id):
                with self.assertRaises(EventValidationError):
                    self.make_event(actor_id=actor_id)

    def test_source_refs_must_be_a_list(self):
        with self.assertRaises(EventValidationError):
            self.make_event(source_refs="workspace://messages/1")

    def test_source_refs_must_have_required_shape(self):
        invalid_source_refs = [
            [{"ref_type": "message", "ref_id": "msg-1"}],
            [{"ref_type": "message", "relationship": "quotes"}],
            [{"ref_id": "msg-1", "relationship": "quotes"}],
            [{"ref_type": "bad", "ref_id": "msg-1", "relationship": "quotes"}],
            [{"ref_type": "message", "ref_id": "msg-1", "relationship": "bad"}],
            ["msg-1"],
        ]

        for source_refs in invalid_source_refs:
            with self.subTest(source_refs=source_refs):
                with self.assertRaises(EventValidationError):
                    self.make_event(source_refs=source_refs)

    def test_original_social_events_may_have_empty_source_refs(self):
        event = self.make_event(source_refs=[])

        self.assertEqual(event["source_refs"], [])

    def test_derived_events_require_source_refs(self):
        with self.assertRaises(EventValidationError):
            self.make_event(
                event_type="extraction.candidate_state.extracted",
                source_refs=[],
            )

    def test_optional_fields_are_allowed_but_not_part_of_event_id(self):
        event = self.make_event()
        event_with_optional = dict(event)
        event_with_optional.update(
            {
                "ts": "2026-06-12T00:00:00Z",
                "subject_ref": "candidate:1",
                "trace_id": "trace:1",
                "causation_id": "aaaw-v1-parent",
                "correlation_id": "corr:1",
            }
        )

        validated = validate_event(event_with_optional)

        self.assertEqual(validated["event_id"], event["event_id"])

    def test_event_id_tampering_rejected(self):
        event = self.make_event()
        event["event_id"] = "aaaw-v1-deadbeef"

        with self.assertRaises(EventValidationError):
            validate_event(event)

    def test_candidate_state_not_authority_false_rejected(self):
        event = self.make_event()
        event["candidate_state_not_authority"] = False

        with self.assertRaises(EventValidationError):
            validate_event(event)

    def test_bool_event_index_rejected(self):
        with self.assertRaises(EventValidationError):
            self.make_event(event_index=True)


if __name__ == "__main__":
    unittest.main()
