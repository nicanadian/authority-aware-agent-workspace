# Architecture

## Layer model

Authority-Aware Agent Workspaces has five layers.

### 1. Social workspace layer

Natural collaboration substrate:

- channels
- messages
- DMs
- mentions
- tasks
- artifact drafts
- comments
- informal disagreements

This layer is intentionally fluent and messy. It is where ideas evolve.

Invariant: social workspace events are non-authoritative.

### 2. Extraction and candidate-state layer

Structured objects proposed from social workspace activity:

- candidate proposal
- candidate task
- candidate blocker
- candidate charter patch
- candidate artifact patch
- candidate evidence reference
- candidate handoff

These objects are useful for review and synthesis, but still not authority.

### 3. Evidence and receipt layer

Evidence objects connect claims to artifacts:

- source message references
- file hashes
- model-call metadata hashes
- artifact hashes
- external URLs, if any
- review notes
- signed or formal receipts in later phases

Default policy: model prompts/responses are hash/metadata-only unless explicitly selected for inclusion.

### 4. Protocol and authority layer

Typed events that may change canonical or authoritative state only when validation passes:

- role_grant_recorded
- proposal_submitted
- blocker_opened
- blocker_resolved
- vote_finalized
- human_approval_recorded
- merge_authorized
- execution_authorized
- execution_receipt_verified

Early phases keep all authority transitions blocked or synthetic. Later phases can add scoped authority fixtures.

### 5. Audit and replay layer

Append-only run records and derived reports:

- event_log.jsonl
- social_messages.jsonl
- candidate_state.jsonl
- evidence_manifest.json
- authority_events.jsonl
- authority_state.json
- evaluator_report.json
- final_summary.md
- replay.html, later

Audit records are not authority. They are evidence for what happened.

## Canonical event envelope

All events should eventually fit a stable envelope:

```json
{
  "event_id": "aaaw-v1-...",
  "schema_version": "aaaw.event.v1",
  "run_id": "...",
  "event_type": "workspace.message.recorded",
  "ts": "2026-...",
  "actor_id": "agent:...",
  "subject_ref": "...",
  "payload": {},
  "source_refs": [],
  "grants_authority": false,
  "authority_effect": "none",
  "candidate_state_not_authority": true
}
```

## First-slice closed event families

Use explicit names that do not imply approval:

- workspace.message.recorded
- workspace.task.proposed
- workspace.artifact_patch.proposed
- chap.candidate_state.extracted
- chap.candidate_state.reviewed
- authority.claim.detected
- authority.claim.blocked
- authority.role_grant.synthetic_recorded
- evidence.receipt.recorded
- evaluator.finding.recorded
- run.manifest.recorded
- run.summary.recorded

Avoid ambiguous names:

- approval.recorded
- release.approved
- blocker.closed
- payment.ready
- deployment.authorized

## Artifact contract for v0 runs

Each deterministic run should write:

```text
run_manifest.json
workspace_events.jsonl
channel_messages.jsonl
tasks.jsonl
artifact_patches.jsonl
candidate_state.jsonl
candidate_state_reviews.jsonl
authority_claims.jsonl
authority_evaluator_report.json
candidate_artifact.md
final_summary.md
```

Optional later artifacts:

```text
model_calls.jsonl
context_exposure_report.json
replay.html
audit_chain_export/
```

## Context modes

The harness should treat context exposure as a condition:

- raw_transcript
- validated_only
- digest_only
- typed_handoff_only
- evidence_only
- poisoned_raw
- redacted_raw
- attribution_blind

## Pressure fixtures

Reusable fixture families:

- fake completion
- stale summary
- side-channel approval
- channel-membership authority confusion
- unsupported evidence claim
- poisoned instruction
- ambiguous ownership
- missing receipt
- overbroad delegation
- expired scope

## Implementation posture

Start deterministic-first:

1. schema + event contract;
2. fixture scenarios;
3. evaluator tests;
4. local CLI run;
5. report artifact;
6. only then live model smoke.
