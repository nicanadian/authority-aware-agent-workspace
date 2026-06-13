# Roadmap

## Phase 0: Planning and repository scaffold

Status: current phase.

Deliverables:

- project vision
- architecture document
- implementation plan
- initial repo structure
- no live model calls

## Phase 1: Deterministic v0 harness

Goal: prove the event model, artifact contract, and authority evaluator without model variance.

Deliverables:

- Python package scaffold
- event envelope dataclasses/Pydantic models
- deterministic scenario loader
- async workspace simulator using scripted agent actions
- closed event allowlist
- authority-boundary evaluator
- fixture scenarios:
  - fake completion
  - stale summary
  - side-channel approval
  - channel-membership authority confusion
  - missing receipt
  - poisoned instruction
- CLI:
  - `aaaw run scenarios/fixtures/side_channel_approval.yaml --out runs/...`
  - `aaaw evaluate runs/...`
- run artifact contract
- unit tests and fixture tests

Success criteria:

- all fixture scenarios produce deterministic run artifacts;
- all authority-laundering attempts are blocked;
- zero events grant authority by accident;
- candidate artifact can still be produced as non-authoritative output;
- tests pass in CI/local.

## Phase 2: Replay and report layer

Goal: make runs inspectable.

Deliverables:

- Markdown run reports
- JSON evaluator reports
- compact HTML replay prototype
- context exposure report
- evidence manifest

Success criteria:

- a reader can answer who claimed what, what evidence existed, and why authority was denied;
- reports distinguish social productivity from protocol safety.

## Phase 3: Live model smoke

Goal: replace scripted actions with one bounded live model path while preserving the artifact contract.

Deliverables:

- provider/model logging
- model_calls.jsonl
- progress.json incremental writes
- parse/repair accounting
- one GPT-5.5/Codex smoke over one scenario

Success criteria:

- model output parses or fails safely;
- malformed output becomes blocker/review state, not success;
- artifact contract unchanged from deterministic Phase 1;
- authority grants remain zero unless explicitly fixture-synthetic.

## Phase 4: Protocol comparison ladder

Goal: compare workspace/control protocols.

Candidate conditions:

- raw_chat_v0
- digest_only_v0
- typed_handoff_v1
- evidence_ledger_v1
- async_forum_v1
- async_forum_extractor_v1
- builder_dao_gate_v1

Metrics:

- unsafe authority accept count
- blocked authority claim count
- evidence-linked candidate-state rate
- artifact completeness
- task liveness
- duplicate/noisy blocker rate
- context byte growth
- model failure/repair rate

## Phase 5: Audit bridge

Goal: import selected run artifacts into a tamper-evident audit root without granting authority.

Deliverables:

- read-only importer or adapter
- deterministic event IDs
- hash-only model-call policy by default
- source mutation proof
- postchecks

Success criteria:

- audit chain verifies;
- blob hashes verify;
- authority_grant_events == 0;
- source run directory is not mutated.

## Phase 6: Human review and answerability

Goal: test whether humans can inspect and challenge candidate state.

Deliverables:

- human review checklist
- blocker family/priority surfaces
- answerability reconstruction task
- loser-consent/post-decision participation measures, where relevant

## Phase 7: Limited scoped authority fixtures

Goal: test formal authority semantics using synthetic or sandboxed capabilities.

Deliverables:

- scoped capability model
- expiry/revocation checks
- exact-match authorization checks
- execution receipt checks
- forbidden-action UI invariants

No real deployment, funds transfer, external publishing, or irreversible actions without explicit human approval.
