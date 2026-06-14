# Authority-Aware Agent Workspaces

Authority-Aware Agent Workspaces is a research and prototyping project for multi-agent collaboration systems where social discussion, candidate state, evidence, and executable authority are kept deliberately separate.

The core thesis:

> Agent collaboration does not mainly need more chat. It needs explicit boundaries between social claims, candidate state, evidence, protocol-valid decisions, and actual authority.

This repository is the unification point for the research threads around CHAP/DAO governance, swarm control-plane ablations, async agent workspaces, context poisoning, typed handoffs, Builder DAO, and tamper-evident audit logs.

## What this project is

A deterministic-first research workbench for building and testing authority-aware collaboration protocols:

- Slack/Discord-style async agent workspace fixtures
- typed event logs and replayable run artifacts
- candidate-state extraction from messy social discourse
- evidence-linked handoffs and receipts
- explicit no-authority checks, blocked authority-claim reports, and sandbox-only synthetic authority positive controls
- pressure fixtures for context poisoning, fake completion, stale summaries, side-channel approval, ambiguous ownership, and overbroad delegation
- deterministic evaluators before broad live model runs
- replay/report artifacts that show who claimed what, what evidence existed, and why authority remained denied

## What this project is not

- Not an autonomous company product.
- Not a DAO that grants real-world authority.
- Not a security claim that agents can govern safely.
- Not a generic chat app.
- Not a live-model benchmark yet.

All generated decisions, blockers, candidate artifacts, and audit records are non-authoritative unless a future explicit authority layer validates a scoped transition.

## Core invariant

Social text is not authority.
Summaries are not authority.
Model output is not authority.
Audit records are not authority.
Candidate state is not authority.

Only protocol-valid, scoped, evidenced, permissioned transitions can mutate authoritative state. Deterministic v0 no-authority fixtures preserve `authority_effect: none` and `candidate_state_not_authority: true`. v0.1 adds a synthetic sandbox positive-control fixture only: it can emit `synthetic_scoped_authority_granted` for scoped formal grant events, but it has no real deployment, funds, publication, or external authority effect.

## Current status

Deterministic v0 is implemented as a local Python package and fixture harness. It can:

```text
scenario json
  -> workspace event/projection artifacts
  -> candidate task/patch/state artifacts
  -> authority-boundary evaluator artifacts
  -> replay/report artifacts
```

Current runs are source-checkout oriented: run commands from the repository root using the checked-out fixtures and package source. No package publication, external service, or live model provider is required.

## Requirements

- Python 3.11 or newer
- No runtime third-party package dependencies
- Standard-library `unittest` test suite

## Quickstart

From the repository root:

```bash
python3.11 -m unittest discover -s tests -v

python3.11 -m authority_workspace.cli run \
  scenarios/fixtures/side_channel_approval.json \
  --out runs/side_channel_approval

python3.11 -m authority_workspace.cli evaluate runs/side_channel_approval
```

The `run` command writes deterministic artifacts. The `evaluate` command validates trusted fixture provenance, re-checks derived outputs, and rewrites evaluator/report artifacts for the run directory.

A bounded one-call live-smoke plumbing path is also available. It requires an explicit provider command as a JSON argv array, executes it without a shell, sends one materialized context JSON request on stdin, and records the result as non-authoritative evidence:

```bash
python3.11 -m authority_workspace.cli live-smoke \
  scenarios/fixtures/side_channel_approval.json \
  --out runs/side_channel_live_smoke \
  --provider-command-json '["/absolute/path/to/provider-wrapper"]' \
  --timeout-seconds 10 \
  --max-context-bytes 8192
```

Provider output is written to `live_model_outputs.jsonl`, scanned for authority-like claims, and blocked like other derived artifacts. The smoke path does not grant authority and is intended only to validate plumbing against one bounded context.

## Artifact overview

A v0 run writes a deterministic artifact surface:

Initial/source artifacts:

- `run_manifest.json`: manifest with scenario metadata, artifact hashes, byte counts, and JSONL line counts
- `workspace_events.jsonl`: canonical non-authority event envelopes and source anchors
- `channel_messages.jsonl`: channel/message projection linked to raw workspace events
- `dm_messages.jsonl`: DM projection linked to raw workspace events
- `context_exposure.jsonl`: deterministic record of exposed context mode/placeholders
- `materialized_contexts.jsonl`: deterministic per-event context surfaces used for prompt/live-smoke plumbing

Candidate artifacts:

- `tasks.jsonl`: non-authoritative candidate task projections
- `artifact_patches.jsonl`: non-authoritative candidate patch projections
- `candidate_state.jsonl`: non-authoritative candidate-state projections
- `candidate_state_reviews.jsonl`: non-authoritative reviews of candidate state

Evaluator/report artifacts:

- `authority_claims.jsonl`: authority-like claims extracted from raw workspace-event payloads and structured candidate artifacts (`tasks.jsonl`, `artifact_patches.jsonl`, `candidate_state.jsonl`, `candidate_state_reviews.jsonl`, and optional `live_model_outputs.jsonl`)
- `authority_state.json`: no-authority state summary
- `authority_evaluator_report.json`: metrics, blocked findings, and unsupported candidate counts
- `evidence_manifest.json`: source/evidence manifest for review
- `replay_timeline.jsonl`: source-linked replay timeline
- `candidate_artifact.md`: non-authority candidate review surface
- `run_report.md`: human-readable non-authority report

## Fixture inventory

The deterministic fixture suite currently contains eight JSON fixtures:

- `scenarios/fixtures/side_channel_approval.json`: DM/social agreement tries to become release approval.
- `scenarios/fixtures/stale_summary.json`: stale digest/signoff language tries to become current approval.
- `scenarios/fixtures/fake_completion.json`: local checklist completion tries to satisfy formal release approval.
- `scenarios/fixtures/channel_membership_authority.json`: channel membership is confused with release authority.
- `scenarios/fixtures/missing_receipt.json`: typed evidence proceeds despite a missing required receipt.
- `scenarios/fixtures/poisoned_instruction.json`: raw text instructs the agent to bypass authority checks.
- `scenarios/fixtures/ambiguous_ownership.json`: ambiguous ownership wording is treated as an authority transfer.
- `scenarios/fixtures/overbroad_delegation.json`: social text attempts broad future-production delegation.

All current fixtures are candidate-only/no-authority fixtures.

## Protocol docs

Current v0 protocol docs live under `protocols/`:

- `protocols/raw_chat_v0.md`
- `protocols/typed_evidence_v0.md`

They specify context exposure, allowed actions, authority restrictions, expected failure modes, and artifact contracts.

## Repository map

```text
authority_workspace/      Python package and CLI
schemas/                  JSON schema docs/placeholders
scenarios/                deterministic fixture scenarios
protocols/                v0 protocol docs
evaluators/               evaluator notes/placeholders
docs/                     vision, architecture, roadmap, plans, reviews
runs/                     local generated run artifacts (gitignored except .gitkeep)
tests/                    unit, fixture, CLI, artifact, and docs tests
```

## Limitations

- One bounded live-smoke plumbing path exists, but there is no broad live-model benchmark or provider-specific adapter yet.
- Positive authority exists only in the synthetic sandbox fixture; it has no real-world authority effect.
- Claim extraction covers raw events plus structured candidate/live-smoke artifacts in v0.1: `workspace_events.jsonl` payloads are scanned first, then candidate JSONL artifacts and optional `live_model_outputs.jsonl` are scanned for unquoted derived authority laundering. Final Markdown reports (`run_report.md`) are not used as a claim source to avoid self-report loops over already-blocked quotes.
- Context modes now produce deterministic materialized context surfaces, but they are still fixture/replay surfaces rather than production prompt pipelines.
- The project is source-checkout oriented; commands assume the repository root and trusted checked-out fixtures.
- Generated reports explain candidate state and blocked claims, but reports themselves are non-authoritative.
