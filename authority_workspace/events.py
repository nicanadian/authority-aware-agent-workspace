"""Canonical event envelope construction and validation."""

from __future__ import annotations

import hashlib
import json
from typing import Any


SCHEMA_VERSION = "aaaw.event.v1"
EVENT_ID_PREFIX = "aaaw-v1-"
AUTHORITY_EFFECT_NONE = "none"

ALLOWED_EVENT_TYPES = frozenset(
    {
        "workspace.message.recorded",
        "workspace.dm.recorded",
        "workspace.task.proposed",
        "workspace.artifact_patch.proposed",
        "workspace.handoff.proposed",
        "extraction.candidate_state.extracted",
        "extraction.candidate_state.reviewed",
        "extraction.handoff.extracted",
        "extraction.handoff.reviewed",
        "evidence.receipt.observed",
        "evaluator.authority_claim.detected",
        "evaluator.authority_claim.blocked",
        "evaluator.scope_claim.detected",
        "evaluator.scope_claim.blocked",
        "evaluator.finding.recorded",
        "run.manifest.recorded",
        "run.summary.recorded",
        "authority.synthetic_grant.recorded",
    }
)

FORBIDDEN_NON_AUTHORITY_EVENT_SUBSTRINGS = (
    "approved",
    "authorized",
    "payment.ready",
    "release.approved",
    "blocker.closed",
    "deployment.authorized",
)

REQUIRED_FIELDS = (
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
)

OPTIONAL_FIELDS = (
    "ts",
    "subject_ref",
    "trace_id",
    "causation_id",
    "correlation_id",
)

ACTOR_ID_PREFIXES = ("agent:", "system:", "evaluator:", "human:")

ORIGINAL_EVENT_TYPES = frozenset(
    {
        "workspace.message.recorded",
        "workspace.dm.recorded",
        "run.manifest.recorded",
        "authority.synthetic_grant.recorded",
    }
)

ALLOWED_SOURCE_REF_TYPES = frozenset(
    {
        "event",
        "message",
        "artifact",
        "file_hash",
        "model_call_hash",
        "external_url",
    }
)

ALLOWED_SOURCE_REF_RELATIONSHIPS = frozenset(
    {
        "derived_from",
        "quotes",
        "supports",
        "contradicts",
        "claims",
        "blocks",
        "requires_review",
    }
)

SOURCE_REF_FIELDS = frozenset({"ref_type", "ref_id", "relationship"})

IDENTITY_FIELDS = (
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
)


class EventValidationError(ValueError):
    """Raised when an event cannot be represented as a valid v0 envelope."""


def create_event(
    *,
    run_id: str,
    event_index: int,
    event_type: str,
    actor_id: str,
    payload: Any,
    source_refs: Any,
    grants_authority: bool = False,
    authority_effect: str = AUTHORITY_EFFECT_NONE,
) -> dict[str, Any]:
    """Create and validate a canonical v0 event envelope."""
    event = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "event_index": event_index,
        "event_type": event_type,
        "actor_id": actor_id,
        "payload": payload,
        "source_refs": source_refs,
        "grants_authority": grants_authority,
        "authority_effect": authority_effect,
        "candidate_state_not_authority": True,
    }
    event["event_id"] = compute_event_id(event)
    return validate_event(event)


def validate_event(event: Any) -> dict[str, Any]:
    """Validate a canonical v0 event envelope and return it unchanged."""
    if not isinstance(event, dict):
        raise EventValidationError("event must be a dict")

    missing = [field for field in REQUIRED_FIELDS if field not in event]
    if missing:
        raise EventValidationError(f"event missing required fields: {', '.join(missing)}")

    extra = [field for field in event if field not in REQUIRED_FIELDS and field not in OPTIONAL_FIELDS]
    if extra:
        raise EventValidationError(f"event contains unknown fields: {', '.join(extra)}")

    if event["schema_version"] != SCHEMA_VERSION:
        raise EventValidationError(f"schema_version must be {SCHEMA_VERSION!r}")

    _validate_non_empty_string(event["run_id"], "run_id")
    _validate_event_index(event["event_index"])
    _validate_event_type(event["event_type"])
    _validate_actor_id(event["actor_id"])
    _validate_source_refs(event["event_type"], event["source_refs"])

    if event["event_type"] == "authority.synthetic_grant.recorded":
        if event["grants_authority"] is not True:
            raise EventValidationError("synthetic grant events must mark grants_authority true")
        if event["authority_effect"] != "synthetic_authority_fixture":
            raise EventValidationError("synthetic grant events must use synthetic_authority_fixture effect")
    else:
        if event["grants_authority"] is not False:
            raise EventValidationError("v0 non-authority events must not grant authority")
        if event["authority_effect"] != AUTHORITY_EFFECT_NONE:
            raise EventValidationError("v0 non-authority authority_effect must be 'none'")

    if event["candidate_state_not_authority"] is not True:
        raise EventValidationError("candidate_state_not_authority must be true")

    computed_event_id = compute_event_id(event)
    if event["event_id"] != computed_event_id:
        raise EventValidationError("event_id does not match canonical event identity")

    return event


def compute_event_id(event: dict[str, Any]) -> str:
    """Compute the deterministic v0 event ID for an event-like mapping."""
    try:
        identity = {field: event[field] for field in IDENTITY_FIELDS}
    except KeyError as exc:
        raise EventValidationError(f"event missing identity field: {exc.args[0]}") from exc

    canonical_bytes = _canonical_json_bytes(identity)
    digest = hashlib.sha256(canonical_bytes).hexdigest()[:32]
    return f"{EVENT_ID_PREFIX}{digest}"


def _canonical_json_bytes(value: Any) -> bytes:
    _ensure_json_compatible(value)
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EventValidationError("event identity must be canonical JSON") from exc


def _ensure_json_compatible(value: Any) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        return
    if isinstance(value, list):
        for item in value:
            _ensure_json_compatible(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise EventValidationError("JSON object keys must be strings")
            _ensure_json_compatible(item)
        return
    raise EventValidationError("event identity must contain only JSON values")


def _validate_non_empty_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise EventValidationError(f"{field_name} must be a non-empty string")


def _validate_actor_id(value: Any) -> None:
    _validate_non_empty_string(value, "actor_id")
    if not any(value.startswith(prefix) and value != prefix for prefix in ACTOR_ID_PREFIXES):
        raise EventValidationError(
            "actor_id must start with agent:, system:, evaluator:, or human:"
        )


def _validate_source_refs(event_type: str, value: Any) -> None:
    if not isinstance(value, list):
        raise EventValidationError("source_refs must be a list")
    if event_type not in ORIGINAL_EVENT_TYPES and not value:
        raise EventValidationError("derived events must include at least one source ref")
    for source_ref in value:
        _validate_source_ref(source_ref)


def _validate_source_ref(value: Any) -> None:
    if not isinstance(value, dict):
        raise EventValidationError("source refs must be objects")
    if set(value) != SOURCE_REF_FIELDS:
        raise EventValidationError("source refs must contain ref_type, ref_id, and relationship")
    ref_type = value["ref_type"]
    ref_id = value["ref_id"]
    relationship = value["relationship"]
    if ref_type not in ALLOWED_SOURCE_REF_TYPES:
        raise EventValidationError(f"unknown source ref type: {ref_type}")
    if relationship not in ALLOWED_SOURCE_REF_RELATIONSHIPS:
        raise EventValidationError(f"unknown source ref relationship: {relationship}")
    _validate_non_empty_string(ref_id, "source ref_id")


def _validate_event_index(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EventValidationError("event_index must be an integer")
    if value < 0:
        raise EventValidationError("event_index must be zero-based and non-negative")


def _validate_event_type(value: Any) -> None:
    _validate_non_empty_string(value, "event_type")
    if _is_ambiguous_non_authority_event_type(value):
        raise EventValidationError("ambiguous authority-like event name is not allowed")
    if value not in ALLOWED_EVENT_TYPES:
        raise EventValidationError(f"unknown event_type: {value}")


def _is_ambiguous_non_authority_event_type(event_type: str) -> bool:
    namespace = event_type.split(".", 1)[0]
    if namespace in {"authority", "evaluator"}:
        return False
    return any(
        forbidden in event_type
        for forbidden in FORBIDDEN_NON_AUTHORITY_EVENT_SUBSTRINGS
    )
