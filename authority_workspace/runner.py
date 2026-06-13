"""Minimal deterministic scenario runner.

Task 6 runner: turns a loaded scenario fixture into raw workspace event and
message artifacts plus a manifest. It deliberately performs no model calls and
creates only non-authoritative v0 event envelopes.
"""

from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any

from authority_workspace.artifacts import build_manifest_entries, write_json, write_jsonl
from authority_workspace.events import create_event
from authority_workspace.scenario import load_scenario


RUNNER_VERSION = "aaaw.runner.minimal.v1"
MANIFEST_SCHEMA_VERSION = "aaaw.run_manifest.v1"
ARTIFACT_SCHEMA_VERSION = "aaaw.artifacts.v1"
INITIAL_ARTIFACT_PATHS = (
    "workspace_events.jsonl",
    "channel_messages.jsonl",
    "dm_messages.jsonl",
    "context_exposure.jsonl",
)


def run_scenario(
    scenario_path: str | Path,
    output_root: str | Path,
    run_id: str = "deterministic-run",
) -> dict[str, Any]:
    """Run *scenario_path* into deterministic raw artifacts under *output_root*."""

    scenario_file = Path(scenario_path)
    scenario = load_scenario(scenario_file)
    root = Path(output_root)

    events = _workspace_events(scenario, run_id)
    event_by_source = _event_by_source(events)
    write_jsonl(root, "workspace_events.jsonl", events)
    write_jsonl(root, "channel_messages.jsonl", _channel_messages(scenario, event_by_source))
    write_jsonl(root, "dm_messages.jsonl", _dm_messages(scenario, event_by_source))
    write_jsonl(root, "context_exposure.jsonl", _context_exposure(scenario, events))

    manifest = _manifest(scenario, scenario_file, root, run_id)
    write_json(root, "run_manifest.json", manifest)
    return manifest


def _workspace_events(scenario: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    """Create one canonical original event per raw channel/DM message."""

    events: list[dict[str, Any]] = []
    event_index = 0
    for channel in scenario["channels"]:
        for message in channel["messages"]:
            events.append(
                create_event(
                    run_id=run_id,
                    event_index=event_index,
                    event_type="workspace.message.recorded",
                    actor_id=message["actor_id"],
                    payload={
                        "channel_id": channel["channel_id"],
                        "message_id": message["message_id"],
                        "text": message["text"],
                        "ts": message["ts"],
                    },
                    source_refs=[],
                )
            )
            event_index += 1
    for thread in scenario["dm_threads"]:
        for message in thread["messages"]:
            events.append(
                create_event(
                    run_id=run_id,
                    event_index=event_index,
                    event_type="workspace.dm.recorded",
                    actor_id=message["actor_id"],
                    payload={
                        "thread_id": thread["thread_id"],
                        "message_id": message["message_id"],
                        "text": message["text"],
                        "ts": message["ts"],
                    },
                    source_refs=[],
                )
            )
            event_index += 1
    return events


def _event_by_source(events: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    mapping: dict[tuple[str, str], str] = {}
    for event in events:
        payload = event["payload"]
        if event["event_type"] == "workspace.message.recorded":
            key = (payload["channel_id"], payload["message_id"])
        else:
            key = (payload["thread_id"], payload["message_id"])
        mapping[key] = event["event_id"]
    return mapping


def _channel_messages(
    scenario: dict[str, Any], event_by_source: dict[tuple[str, str], str]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for channel in scenario["channels"]:
        for message in channel["messages"]:
            records.append(
                {
                    "channel_id": channel["channel_id"],
                    "channel_title": channel["title"],
                    "message_id": message["message_id"],
                    "actor_id": message["actor_id"],
                    "text": message["text"],
                    "ts": message["ts"],
                    "source_event_id": event_by_source[(channel["channel_id"], message["message_id"])],
                    "source_event_ids": [event_by_source[(channel["channel_id"], message["message_id"])]],
                    "grants_authority": False,
                    "authority_effect": "none",
                    "candidate_state_not_authority": True,
                }
            )
    return records


def _dm_messages(
    scenario: dict[str, Any], event_by_source: dict[tuple[str, str], str]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for thread in scenario["dm_threads"]:
        for message in thread["messages"]:
            records.append(
                {
                    "thread_id": thread["thread_id"],
                    "participants": list(thread["participants"]),
                    "message_id": message["message_id"],
                    "actor_id": message["actor_id"],
                    "text": message["text"],
                    "ts": message["ts"],
                    "authority_note": thread.get("authority_note", ""),
                    "source_event_id": event_by_source[(thread["thread_id"], message["message_id"])],
                    "source_event_ids": [event_by_source[(thread["thread_id"], message["message_id"])]],
                    "grants_authority": False,
                    "authority_effect": "none",
                    "candidate_state_not_authority": True,
                }
            )
    return records


def _context_exposure(scenario: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    visible_event_ids = [event["event_id"] for event in events]
    visible_channel_message_ids = [
        message["message_id"]
        for channel in scenario["channels"]
        for message in channel["messages"]
    ]
    visible_dm_message_ids = [
        message["message_id"]
        for thread in scenario["dm_threads"]
        for message in thread["messages"]
    ]
    deterministic_context = {
        "scenario_id": scenario["scenario_id"],
        "protocol": scenario["protocol"],
        "context_mode": scenario["context_mode"],
        "visible_event_ids": visible_event_ids,
        "visible_channel_message_ids": visible_channel_message_ids,
        "visible_dm_message_ids": visible_dm_message_ids,
    }
    deterministic_context_bytes = len(
        str(sorted(deterministic_context.items())).encode("utf-8")
    )
    return [
        {
            "exposure_id": "context:initial:raw-workspace",
            "actor_id": "system:runner",
            "protocol": scenario["protocol"],
            "context_mode": scenario["context_mode"],
            "visible_event_ids": visible_event_ids,
            "visible_channel_message_ids": visible_channel_message_ids,
            "visible_dm_message_ids": visible_dm_message_ids,
            "hidden_canonical_state_refs": [],
            "poison_markers_visible": [],
            "context_bytes": deterministic_context_bytes,
            "deterministic_placeholder": True,
            "source_event_ids": visible_event_ids,
            "grants_authority": False,
            "authority_effect": "none",
            "candidate_state_not_authority": True,
        }
    ]


def _manifest(
    scenario: dict[str, Any],
    scenario_path: Path,
    output_root: Path,
    run_id: str,
) -> dict[str, Any]:
    scenario_bytes = scenario_path.read_bytes()
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "scenario_id": scenario["scenario_id"],
        "scenario_sha256": "sha256:" + hashlib.sha256(scenario_bytes).hexdigest(),
        "fixture_type": scenario["fixture_type"],
        "protocol": scenario["protocol"],
        "context_mode": scenario["context_mode"],
        "seed": scenario["seed"],
        "runner_version": RUNNER_VERSION,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifacts": build_manifest_entries(output_root, INITIAL_ARTIFACT_PATHS),
    }


__all__ = ["INITIAL_ARTIFACT_PATHS", "RUNNER_VERSION", "run_scenario"]
