"""Deterministic scenario fixture loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROTOCOLS = {"raw_chat_v0", "typed_evidence_v0"}
CONTEXT_MODES = {
    "raw_transcript",
    "validated_only",
    "digest_only",
    "typed_handoff_only",
    "evidence_only",
    "poisoned_raw",
    "redacted_raw",
    "attribution_blind",
}
FIXTURE_TYPES = {
    "side_channel_approval",
    "stale_summary",
    "fake_completion",
    "channel_membership_authority",
    "missing_receipt",
    "poisoned_instruction",
    "ambiguous_ownership",
    "overbroad_delegation",
    "synthetic_authority_controls",
}
LIST_FIELDS = (
    "channels",
    "dm_threads",
    "tasks",
    "artifact_drafts",
    "handoffs",
    "scripted_events",
)
REQUIRED_FIELDS = (
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
)


def load_scenario(path: str | Path) -> dict[str, Any]:
    """Load and minimally validate a scenario JSON file.

    The supplied path is the only filesystem location used by the loader;
    the scenario_id field is treated as data, never as a path component.
    """

    scenario_path = Path(path)
    try:
        with scenario_path.open(encoding="utf-8") as scenario_file:
            scenario = json.load(scenario_file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON in {scenario_path}") from exc

    if not isinstance(scenario, dict):
        raise ValueError("scenario must be a JSON object")

    _validate_required_fields(scenario)
    _validate_non_empty_string(scenario["scenario_id"], "scenario_id")
    _validate_non_empty_string(scenario["title"], "title")
    _validate_fixture_type(scenario["fixture_type"])
    _validate_protocol(scenario["protocol"])
    _validate_context_mode(scenario["context_mode"])
    _validate_seed(scenario["seed"])
    _validate_agent_ids(scenario["agents"])
    _validate_list_fields(scenario)
    _validate_synthetic_scripted_events(scenario)

    return scenario


def _validate_required_fields(scenario: dict[str, Any]) -> None:
    for field_name in REQUIRED_FIELDS:
        if field_name not in scenario:
            raise ValueError(f"missing required field: {field_name}")


def _validate_non_empty_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _validate_fixture_type(fixture_type: Any) -> None:
    if not isinstance(fixture_type, str) or fixture_type not in FIXTURE_TYPES:
        raise ValueError(f"unknown fixture type: {fixture_type}")


def _validate_protocol(protocol: Any) -> None:
    if not isinstance(protocol, str) or protocol not in PROTOCOLS:
        raise ValueError(f"unknown protocol: {protocol}")


def _validate_context_mode(context_mode: Any) -> None:
    if not isinstance(context_mode, str) or context_mode not in CONTEXT_MODES:
        raise ValueError(f"unknown context mode: {context_mode}")


def _validate_seed(seed: Any) -> None:
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer")


def _validate_agent_ids(agents: Any) -> None:
    if not isinstance(agents, list) or not agents:
        raise ValueError("agents must be a non-empty list")

    seen = set()
    for agent_id in agents:
        if not isinstance(agent_id, str) or not agent_id:
            raise ValueError("agent ids must be non-empty strings")
        if agent_id in seen:
            raise ValueError(f"duplicate agent id: {agent_id}")
        seen.add(agent_id)


def _validate_list_fields(scenario: dict[str, Any]) -> None:
    for field_name in LIST_FIELDS:
        if not isinstance(scenario[field_name], list):
            raise ValueError(f"{field_name} must be a list")


def _validate_synthetic_scripted_events(scenario: dict[str, Any]) -> None:
    for scripted_event in scenario["scripted_events"]:
        if not isinstance(scripted_event, dict):
            raise ValueError("scripted_events entries must be objects")
        if scripted_event.get("event_type") == "authority.synthetic_grant.recorded" and scenario["fixture_type"] != "synthetic_authority_controls":
            raise ValueError("synthetic grant scripted events require fixture_type synthetic_authority_controls")


__all__ = [
    "CONTEXT_MODES",
    "FIXTURE_TYPES",
    "LIST_FIELDS",
    "PROTOCOLS",
    "REQUIRED_FIELDS",
    "load_scenario",
]
