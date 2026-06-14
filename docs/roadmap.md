# Roadmap

## Phase 0: Planning and repository scaffold

Status: complete.

Delivered:

- project vision
- architecture document
- implementation plan
- initial repository structure
- deterministic-first/no-live-model policy for v0

## Phase 1: Deterministic v0 harness

Status: complete for deterministic v0.

Goal: prove the event model, artifact contract, and authority evaluator without model variance.

Delivered:

- Python package scaffold requiring Python 3.11+
- deterministic JSON scenario loader
- event envelope and artifact writers
- async-workspace-style scripted event/projection artifacts
- closed fixture/protocol/context allowlists
- authority-boundary evaluator
- fixture scenarios:
  - side-channel approval
  - stale summary
  - fake completion
  - channel-membership authority confusion
  - missing receipt
  - poisoned instruction
  - ambiguous ownership
  - overbroad delegation
- CLI:
  - `python3.11 -m authority_workspace.cli run scenarios/fixtures/side_channel_approval.json --out runs/side_channel_approval`
  - `python3.11 -m authority_workspace.cli evaluate runs/side_channel_approval`
- run artifact contract with manifest hashes, byte counts, and JSONL line counts
- unit, fixture, CLI, artifact, protocol-doc, and CI-workflow tests

Success criteria:

- all fixture scenarios produce deterministic run artifacts;
- all current authority-laundering attempts are blocked;
- zero events grant authority by accident;
- candidate artifacts can still be produced as non-authoritative output;
- tests pass in CI/local.

## Phase 2: Replay and report layer

Status: complete for deterministic v0 report artifacts.

Goal: make runs inspectable.

Delivered:

- Markdown run reports
- JSON evaluator reports
- source-linked replay timeline
- context exposure records
- evidence manifest
- candidate artifact review surface

Success criteria:

- a reader can answer who claimed what, what evidence existed, and why authority was denied;
- reports distinguish social productivity from protocol safety;
- reports remain non-authoritative.

Future extension:

- compact HTML replay prototype, if useful after public handoff.

## CI and public handoff readiness

Status: current/completed baseline.

Current CI/local validation covers package import, scenario loading, event/artifact invariants, evaluator behavior, reports, CLI behavior, protocol documentation, and workflow configuration.

Current handoff focus:

- v0.1 documentation hygiene;
- fixture inventory clarity;
- public-readiness notes and limitations;
- preserving `docs/research-ideas.md` as a future research note.

## Next milestone: v0.1 docs, handoff, and public readiness

Goal: make deterministic v0 understandable from a fresh source checkout.

Deliverables:

- README quickstart/status/limitations aligned with current code;
- roadmap aligned with completed deterministic v0 and future live-model work;
- fixture inventories in README and `scenarios/README.md`;
- protocol index aligned with current v0 docs;
- future-research note retained without implying implemented scope.

Success criteria:

- a new reader can run tests, run a fixture, evaluate the run, and inspect artifacts;
- docs clearly state no live model evidence and no positive authority path;
- docs do not imply real authority, real deployment, or model-backed safety evidence.

## Phase 3: Live model smoke

Status: future.

Goal: replace scripted actions with one bounded live model path while preserving the artifact contract.

Deliverables:

- provider/model logging
- `model_calls.jsonl`
- `progress.json` incremental writes
- parse/repair accounting
- one bounded live-model smoke over one scenario

Success criteria:

- model output parses or fails safely;
- malformed output becomes blocker/review state, not success;
- artifact contract remains compatible with deterministic v0;
- authority grants remain zero unless an explicit future scoped-authority fixture says otherwise.

## Phase 4: Protocol comparison ladder

Status: future.

Goal: compare workspace/control protocols.

Candidate conditions:

- `raw_chat_v0`
- `digest_only_v0`
- `typed_handoff_v1`
- `typed_evidence_v0`
- `evidence_ledger_v1`
- `async_forum_v1`
- `async_forum_extractor_v1`
- `builder_dao_gate_v1`

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

Status: future.

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

Status: future.

Goal: test whether humans can inspect and challenge candidate state.

Deliverables:

- human review checklist
- blocker family/priority surfaces
- answerability reconstruction task
- loser-consent/post-decision participation measures, where relevant

## Phase 7: Limited scoped authority fixtures

Status: future.

Goal: test formal authority semantics using synthetic or sandboxed capabilities.

Deliverables:

- scoped authority fixtures
- scoped capability model
- expiry/revocation checks
- exact-match authorization checks
- execution receipt checks
- forbidden-action UI invariants

No real deployment, funds transfer, external publishing, or irreversible actions without explicit human approval.
