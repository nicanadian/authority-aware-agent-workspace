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
from authority_workspace.evaluator import EVALUATOR_OUTPUT_PATHS, evaluate_run
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
CANDIDATE_ARTIFACT_PATHS = (
    "tasks.jsonl",
    "artifact_patches.jsonl",
    "candidate_state.jsonl",
    "candidate_state_reviews.jsonl",
)
RUN_ARTIFACT_PATHS = (*INITIAL_ARTIFACT_PATHS, *CANDIDATE_ARTIFACT_PATHS, *EVALUATOR_OUTPUT_PATHS)


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
    candidate_outputs = _candidate_outputs(scenario, events)
    write_jsonl(root, "tasks.jsonl", candidate_outputs["tasks"])
    write_jsonl(root, "artifact_patches.jsonl", candidate_outputs["artifact_patches"])
    write_jsonl(root, "candidate_state.jsonl", candidate_outputs["candidate_state"])
    write_jsonl(root, "candidate_state_reviews.jsonl", candidate_outputs["candidate_state_reviews"])

    manifest = _manifest(scenario, scenario_file, root, run_id, (*INITIAL_ARTIFACT_PATHS, *CANDIDATE_ARTIFACT_PATHS))
    write_json(root, "run_manifest.json", manifest)

    evaluate_run(root)

    manifest = _manifest(scenario, scenario_file, root, run_id, RUN_ARTIFACT_PATHS)
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


def _candidate_outputs(scenario: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Build deterministic non-authoritative candidate projections."""

    tasks: list[dict[str, Any]] = []
    artifact_patches: list[dict[str, Any]] = []
    candidate_state: list[dict[str, Any]] = []
    candidate_state_reviews: list[dict[str, Any]] = []

    for task in scenario.get("tasks", []):
        candidate_id = f"candidate:task:{task['task_id']}"
        task_source_event_ids = _task_source_event_ids(task, events)
        if task_source_event_ids:
            base = _candidate_base(candidate_id, "candidate_task", "task", task_source_event_ids)
            review_base = _candidate_base(f"review:{candidate_id}", "candidate_state_review", "task", task_source_event_ids)
            review_status = "evidence_linked"
        else:
            unsupported_reason = "task projection is not backed by immutable workspace event evidence"
            base = _unsupported_candidate_base(candidate_id, "candidate_task", "task", unsupported_reason)
            review_base = _unsupported_candidate_base(
                f"review:{candidate_id}", "candidate_state_review", "task", unsupported_reason
            )
            review_status = "unsupported"
        tasks.append(
            {
                **base,
                "task_id": task["task_id"],
                "title": task["title"],
                "owner": task["owner"],
                "assignee": task["assignee"],
                "required_authority": task["required_authority"],
                "candidate_status": task["status"],
            }
        )
        candidate_state.append(
            {
                **base,
                "state_scope": "candidate",
                "state_kind": "task",
                "subject_id": task["task_id"],
                "candidate_status": task["status"],
                "mutates_authority_state": False,
            }
        )
        candidate_state_reviews.append(
            {
                **review_base,
                "reviewed_candidate_id": candidate_id,
                "review_status": review_status,
                "state_scope": "candidate",
                "mutates_authority_state": False,
            }
        )

    for draft in scenario.get("artifact_drafts", []):
        patch_id = f"candidate:artifact_patch:{draft['artifact_id']}"
        unsupported_reason = "fixture artifact draft is not backed by an immutable workspace event in v0"
        artifact_patches.append(
            {
                **_unsupported_candidate_base(patch_id, "candidate_artifact_patch", "artifact_patch", unsupported_reason),
                "patch_id": patch_id,
                "artifact_id": draft["artifact_id"],
                "task_id": draft["task_id"],
                "author": draft["author"],
                "operation": "propose_draft_content",
                "content": draft["content"],
                "candidate_status": draft["status"],
            }
        )
        state_candidate_id = f"candidate:state:{draft['artifact_id']}"
        candidate_state.append(
            {
                **_unsupported_candidate_base(state_candidate_id, "candidate_state", "artifact_patch", unsupported_reason),
                "state_scope": "candidate",
                "state_kind": "artifact",
                "subject_id": draft["artifact_id"],
                "candidate_status": draft["status"],
                "mutates_authority_state": False,
            }
        )
        candidate_state_reviews.append(
            {
                **_unsupported_candidate_base(
                    f"review:{state_candidate_id}",
                    "candidate_state_review",
                    "artifact_patch",
                    "candidate state projection lacks immutable workspace event evidence",
                ),
                "reviewed_candidate_id": state_candidate_id,
                "state_scope": "candidate",
                "mutates_authority_state": False,
            }
        )

    return {
        "tasks": tasks,
        "artifact_patches": artifact_patches,
        "candidate_state": candidate_state,
        "candidate_state_reviews": candidate_state_reviews,
    }


def _task_source_event_ids(task: dict[str, Any], events: list[dict[str, Any]]) -> list[str]:
    """Find raw event evidence that semantically introduces the task."""

    title_terms = [term for term in task["title"].lower().replace(":", " ").split() if len(term) > 3]
    for event in events:
        text = event.get("payload", {}).get("text", "").lower()
        if title_terms and all(term in text for term in title_terms[:2]):
            return [event["event_id"]]
    return []


def _evidence_refs(source_event_ids: list[str]) -> list[dict[str, str]]:
    return [
        {"ref_type": "event", "ref_id": event_id, "relationship": "supports"}
        for event_id in source_event_ids
    ]


def _candidate_base(candidate_id: str, projection_type: str, candidate_type: str, source_event_ids: list[str]) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "projection_type": projection_type,
        "source_event_ids": list(source_event_ids),
        "evidence_refs": _evidence_refs(source_event_ids),
        "extraction_method": "scripted_fixture",
        "review_status": "accepted_candidate",
        "grants_authority": False,
        "authority_effect": "none",
        "candidate_state_not_authority": True,
    }


def _unsupported_candidate_base(candidate_id: str, projection_type: str, candidate_type: str, reason: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "projection_type": projection_type,
        "source_event_ids": [],
        "evidence_refs": [],
        "extraction_method": "scripted_fixture",
        "review_status": "unsupported",
        "unsupported_reason": reason,
        "grants_authority": False,
        "authority_effect": "none",
        "candidate_state_not_authority": True,
    }


def _manifest(
    scenario: dict[str, Any],
    scenario_path: Path,
    output_root: Path,
    run_id: str,
    artifact_paths: tuple[str, ...],
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
        "artifacts": build_manifest_entries(output_root, artifact_paths),
    }


__all__ = ["CANDIDATE_ARTIFACT_PATHS", "INITIAL_ARTIFACT_PATHS", "RUN_ARTIFACT_PATHS", "RUNNER_VERSION", "run_scenario"]
