"""Scenario fixture loader tests."""

import json
import tempfile
import unittest
from pathlib import Path

from authority_workspace.scenario import (
    CONTEXT_MODES,
    PROTOCOLS,
    load_scenario,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDE_CHANNEL_FIXTURE = REPO_ROOT / "scenarios" / "fixtures" / "side_channel_approval.json"


class ScenarioLoaderTests(unittest.TestCase):
    def write_scenario(self, scenario, name="scenario.json"):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / name
        path.write_text(json.dumps(scenario), encoding="utf-8")
        return path

    def valid_scenario(self, **overrides):
        scenario = {
            "scenario_id": "unit-test-scenario",
            "title": "Unit Test Scenario",
            "fixture_type": "side_channel_approval",
            "protocol": "raw_chat_v0",
            "context_mode": "raw_transcript",
            "seed": 7,
            "agents": ["agent:coordinator", "agent:reviewer"],
            "channels": [],
            "dm_threads": [],
            "tasks": [],
            "artifact_drafts": [],
            "handoffs": [],
            "scripted_events": [],
        }
        scenario.update(overrides)
        return scenario

    def test_loader_returns_scenario_id_title_agents_protocol_and_context_mode(self):
        scenario = load_scenario(SIDE_CHANNEL_FIXTURE)

        self.assertEqual(scenario["scenario_id"], "side_channel_approval")
        self.assertEqual(scenario["title"], "Side-channel approval is not authority")
        self.assertEqual(scenario["fixture_type"], "side_channel_approval")
        self.assertEqual(scenario["protocol"], "raw_chat_v0")
        self.assertEqual(scenario["context_mode"], "raw_transcript")
        self.assertEqual(
            scenario["agents"],
            ["agent:alex", "agent:blair", "agent:casey"],
        )

    def test_side_channel_fixture_contains_dm_social_agreement_but_no_authority(self):
        scenario = load_scenario(SIDE_CHANNEL_FIXTURE)
        encoded = json.dumps(scenario, sort_keys=True).lower()

        self.assertTrue(scenario["channels"])
        self.assertTrue(scenario["dm_threads"])
        self.assertTrue(scenario["tasks"])
        self.assertTrue(scenario["artifact_drafts"])
        self.assertIn("approved", encoded)
        self.assertIn("dm", encoded)
        self.assertNotIn('"grants_authority": true', encoded)
        self.assertNotIn('"authority_effect": "granted"', encoded)

    def test_malformed_json_errors_deterministically(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "broken.json"
        path.write_text('{"scenario_id": ', encoding="utf-8")

        with self.assertRaises(ValueError) as raised:
            load_scenario(path)

        self.assertEqual(str(raised.exception), f"malformed JSON in {path}")

    def test_missing_required_fields_raise_value_error(self):
        scenario = self.valid_scenario()
        del scenario["scripted_events"]

        with self.assertRaisesRegex(ValueError, "missing required field: scripted_events"):
            load_scenario(self.write_scenario(scenario))

    def test_duplicate_agent_ids_raise_value_error(self):
        scenario = self.valid_scenario(agents=["agent:alex", "agent:alex"])

        with self.assertRaisesRegex(ValueError, "duplicate agent id: agent:alex"):
            load_scenario(self.write_scenario(scenario))

    def test_empty_agents_rejected(self):
        scenario = self.valid_scenario(agents=[])

        with self.assertRaisesRegex(ValueError, "agents must be a non-empty list"):
            load_scenario(self.write_scenario(scenario))

    def test_non_string_agent_ids_rejected_deterministically(self):
        scenario = self.valid_scenario(agents=["agent:alex", {"bad": "agent"}])

        with self.assertRaisesRegex(ValueError, "agent ids must be non-empty strings"):
            load_scenario(self.write_scenario(scenario))

    def test_required_async_workspace_fields_must_be_lists(self):
        for field_name in ("channels", "dm_threads", "tasks", "artifact_drafts", "handoffs", "scripted_events"):
            with self.subTest(field_name=field_name):
                scenario = self.valid_scenario(**{field_name: "not-a-list"})
                with self.assertRaisesRegex(ValueError, f"{field_name} must be a list"):
                    load_scenario(self.write_scenario(scenario))

    def test_unknown_fixture_type_rejected(self):
        scenario = self.valid_scenario(fixture_type="not_a_fixture")

        with self.assertRaisesRegex(ValueError, "unknown fixture type: not_a_fixture"):
            load_scenario(self.write_scenario(scenario))

    def test_negative_seed_rejected(self):
        scenario = self.valid_scenario(seed=-1)

        with self.assertRaisesRegex(ValueError, "seed must be a non-negative integer"):
            load_scenario(self.write_scenario(scenario))

    def test_empty_string_identity_fields_rejected(self):
        for field_name in ("scenario_id", "title"):
            with self.subTest(field_name=field_name):
                scenario = self.valid_scenario(**{field_name: ""})
                with self.assertRaisesRegex(ValueError, f"{field_name} must be a non-empty string"):
                    load_scenario(self.write_scenario(scenario))

    def test_unknown_protocol_rejected(self):
        scenario = self.valid_scenario(protocol="email_v9")

        with self.assertRaisesRegex(ValueError, "unknown protocol: email_v9"):
            load_scenario(self.write_scenario(scenario))

    def test_non_string_enum_values_rejected_deterministically(self):
        cases = (
            ("fixture_type", [], "unknown fixture type"),
            ("protocol", [], "unknown protocol"),
            ("context_mode", [], "unknown context mode"),
        )
        for field_name, value, expected_error in cases:
            with self.subTest(field_name=field_name):
                scenario = self.valid_scenario(**{field_name: value})
                with self.assertRaisesRegex(ValueError, expected_error):
                    load_scenario(self.write_scenario(scenario))

    def test_unknown_context_mode_rejected(self):
        scenario = self.valid_scenario(context_mode="telepathy")

        with self.assertRaisesRegex(ValueError, "unknown context mode: telepathy"):
            load_scenario(self.write_scenario(scenario))

    def test_scenario_ids_are_not_used_as_filesystem_paths(self):
        scenario = self.valid_scenario(scenario_id="../outside/not-a-file")

        loaded = load_scenario(self.write_scenario(scenario))

        self.assertEqual(loaded["scenario_id"], "../outside/not-a-file")

    def test_known_protocols_and_context_modes_match_plan(self):
        self.assertEqual(PROTOCOLS, {"raw_chat_v0", "typed_evidence_v0"})
        self.assertEqual(
            CONTEXT_MODES,
            {
                "raw_transcript",
                "validated_only",
                "digest_only",
                "typed_handoff_only",
                "evidence_only",
                "poisoned_raw",
                "redacted_raw",
                "attribution_blind",
            },
        )


if __name__ == "__main__":
    unittest.main()
