# Council Review: Authority-Aware Agent Workspace v0 Plan

Review target:

- `docs/plans/0001-authority-aware-agent-workspace-v0.md`
- `docs/architecture.md`
- `docs/vision.md`
- `docs/roadmap.md`
- `docs/research-lineage.md`

Review date: 2026-06-12

## Council verdict

Proceed, but patch the plan before implementation.

The council agreed that the project direction is strong: deterministic-first, authority-aware, candidate-state-not-authority, and aligned with the prior DAO/CHAP, swarm, async-workspace, handoff, Ark, Builder DAO, and hermes-auditd lessons.

However, the plan is not yet strict enough to support credible research claims. The main risk is building a harness that proves only that known fixture labels were blocked, rather than proving that authority claims were detected across raw social text, derived candidate state, evidence, reports, receipts, and future live-model outputs.

The plan should be hardened before code implementation.

## Reviewers

Six independent perspectives reviewed the plan:

1. Research methodology / experiment design
2. Architecture / API / event model
3. Security / authority-laundering safety
4. Implementation / TDD / project execution
5. Product / replay / human review UX
6. Prior research integration / lineage consistency

## Highest-priority required patches

### 1. Add a research design and measurement contract

Severity: BLOCKER

The current v0 plan is a good engineering scaffold but not yet a clean experiment.

Add a section defining:

- experimental unit: one scenario run
- treatment variables: protocol, context_mode, fixture_type, seed
- outcome variables:
  - unsafe authority accept count
  - blocked authority claim count
  - false accept count
  - false reject count
  - valid synthetic authority accept count, if synthetic fixtures exist
  - evidence-linked candidate-state rate
  - unsupported candidate-state count
  - orphan source reference count
  - authority state changed by invalid claim: yes/no
- ground-truth labels:
  - invalid_authority_claims
  - valid_authority_transitions
  - required_receipts
  - expected_candidate_outputs
- what v0 can claim:
  - included deterministic fixture attempts were blocked
- what v0 cannot claim:
  - real-world agent governance safety
  - adversarial completeness
  - human usability
  - live-model robustness

### 2. Add positive controls or explicitly remove authority-acceptance from v0

Severity: BLOCKER

The current plan says every event has `grants_authority: false` unless it is an explicitly synthetic test fixture grant, but the synthetic event is not consistently defined.

Choose one:

Option A, recommended for v0:

- all v0 events have `grants_authority: false`
- no synthetic grant exception in v0
- scoped/synthetic authority acceptance moves to v0.1 or Phase 7

Option B:

- add a formal synthetic positive-control fixture
- define `authority.role_grant.synthetic_recorded` or preferably `authority_fixture.role_grant.synthetic_recorded`
- split counts:
  - real_authority_grant_events
  - synthetic_authority_fixture_events
  - blocked_authority_claim_events
- require synthetic grants to be scoped by principal/action/target/expiry
- prove social/candidate/evidence/audit layers cannot emit them

Without a positive control, the system may be merely authority-denying rather than authority-aware.

### 3. Prevent evaluator overfitting to fixture names

Severity: BLOCKER

The evaluator must not consume `expected_blocked_claims` or scenario IDs as detection inputs.

Patch the plan to require:

- ground-truth labels live in oracle/test metadata, not runner/evaluator runtime inputs
- evaluator detects from event semantics and raw text fields
- tests rename scenarios while preserving semantics
- paraphrased fixtures still block:
  - “approved”
  - “greenlit”
  - “good to ship”
  - “legal is done”
  - “everyone agreed”
  - “no blockers”
  - “receipt attached so proceed”
- evaluator cannot pass by matching `side_channel_approval` strings

### 4. Score raw streams before sanitized/derived artifacts

Severity: BLOCKER

A dangerous failure mode is: raw social text contains an authority claim, extractor drops or sanitizes it, evaluator scores only the sanitized candidate state, and the run passes.

Add this invariant:

> The evaluator must score immutable raw event streams before any summarization, redaction, repair, candidate extraction, or report generation.

Tests should assert:

- raw event contains an approval/authorization claim
- candidate extractor drops or neutralizes it
- evaluator still detects and blocks it from raw events

The detector should scan all text-bearing raw and derived surfaces:

- workspace_events.jsonl payloads
- channel_messages.jsonl
- tasks.jsonl
- artifact_patches.jsonl
- candidate_state.jsonl
- candidate_state_reviews.jsonl
- authority_claims.jsonl
- authority_evaluator_report.json
- candidate_artifact.md
- final_summary.md or run_report.md
- future parse/repair/live model outputs

### 5. Define one canonical event envelope

Severity: HIGH

The plan and architecture currently differ. Architecture includes `ts` and `subject_ref`; the implementation plan does not.

Patch with a single v0 envelope.

Recommended required fields:

```json
{
  "event_id": "aaaw-v1-...",
  "schema_version": "aaaw.event.v1",
  "run_id": "...",
  "event_index": 0,
  "event_type": "workspace.message.recorded",
  "actor_id": "agent:founder",
  "payload": {},
  "source_refs": [],
  "grants_authority": false,
  "authority_effect": "none",
  "candidate_state_not_authority": true
}
```

Optional:

```json
{
  "ts": "...",
  "subject_ref": "...",
  "trace_id": "...",
  "causation_id": "...",
  "correlation_id": "..."
}
```

Define event ID hashing over canonical JSON, not string concatenation:

- UTF-8
- `sort_keys=True`
- `separators=(",", ":")`
- no NaN/Infinity
- include schema_version, run_id, event_index, event_type, actor_id, payload, source_refs, grants_authority, authority_effect, candidate_state_not_authority

### 6. Add an explicit artifact contract table

Severity: HIGH

Current artifacts are listed, but record shapes and routing are not defined.

Add a table with:

- file name
- required/optional
- JSON/JSONL/Markdown
- record type
- full envelope vs derived projection
- source event types
- ordering rule
- whether empty file is allowed

Clarify:

- `workspace_events.jsonl` is the complete append-only event log
- other JSONL files are derived projections unless stated otherwise
- every derived record must carry `source_event_id` or `source_event_ids`
- manifest includes schema versions, scenario hash, file hashes, byte sizes, and JSONL line counts

### 7. Add `authority_state.json` to v0 outputs

Severity: HIGH

The architecture mentions authority state; the plan does not require it.

Add:

```text
authority_state.json
```

It should make “no authority transition occurred” directly inspectable.

Tests:

- invalid social claim cannot change authority_state
- evidence receipt cannot change authority_state
- manifest verification cannot change authority_state
- evaluator finding cannot change authority_state

### 8. Add evidence and source-reference contracts

Severity: HIGH

Evidence-linking is the central CHAP lesson, but v0 does not yet require enough evidence structure.

Every candidate object should include:

- candidate_id
- source_event_ids
- evidence_refs
- extraction_method
- review_status
- authority_effect: none
- candidate_state_not_authority: true

Every authority finding should include:

- finding_id
- claim_id
- claim_type
- claim_text or normalized_claim
- actor_id
- source_event_ids
- evidence_refs
- asserted_action
- asserted_target
- asserted_scope
- required_rule
- failure_reason
- decision
- human_explanation

Add `evidence_manifest.json` in v0, not later:

- evidence_id
- evidence_type: message / artifact_hash / receipt / review_note / external_url
- source_event_id
- artifact path/hash, if applicable
- excerpt/snippet if safe
- availability: inline / hash_only / unavailable
- supports_claim_ids
- limitations

### 9. Add context exposure logging to v0

Severity: HIGH

The project’s prior research treats context exposure as an experimental treatment. The plan lists context modes but does not enforce them in v0.

Add a v0 artifact:

```text
context_exposure.jsonl
```

or minimally:

```text
context_exposure_report.json
```

For every scripted or future live agent action, record:

- actor
- protocol
- context_mode
- visible event IDs
- visible channel/message IDs
- hidden canonical state excluded
- injected/poisoned context markers
- prompt/context byte count placeholder for deterministic runs
- real prompt/context byte count for live runs

### 10. Preserve async workspace structure in scenario schema

Severity: HIGH

The plan’s scenario schema is too flat for the project’s async-workspace ambition.

Add explicit scenario sections:

```json
{
  "channels": [],
  "dm_threads": [],
  "tasks": [],
  "artifact_drafts": [],
  "handoffs": [],
  "scripted_events": []
}
```

Tests should prove:

- side-channel/DM agreements are recorded socially
- side-channel/DM agreements cannot update canonical authority state
- channel membership cannot imply authority

### 11. Promote handoff/delegation fixtures earlier

Severity: MEDIUM-HIGH

Handoff Lab lessons are central. The current v0 has ambiguous ownership and overbroad delegation only in architecture, not plan fixtures.

Add v0.1 or stretch fixtures:

- ambiguous ownership
- overbroad delegation
- scoped packet missing evidence
- acceptance without authority

Candidate events:

- workspace.handoff.proposed
- extraction.handoff.extracted
- extraction.handoff.reviewed
- evaluator.scope_claim.detected
- evaluator.scope_claim.blocked

### 12. Improve task sequencing

Severity: HIGH

Current Task 5 runner requires evaluator and report artifacts before evaluator/report tasks exist.

Patch the implementation plan sequence:

1. package scaffold + pyproject
2. event envelope
3. contracts/schemas for scenario, findings, manifest, source refs
4. scenario loader + one side-channel fixture
5. artifact writer split into:
   - JSONL writer
   - safe output-root path resolver
   - manifest/hash writer
6. minimal runner writes raw events + manifest only
7. evaluator for side-channel only
8. runner integrates evaluator report
9. add remaining fixtures one at a time
10. report generator
11. CLI
12. protocol docs/schemas
13. CI early, not last

### 13. Strengthen filesystem/artifact safety tests

Severity: MEDIUM-HIGH

Add tests for:

- absolute paths rejected
- `..` rejected
- symlinks escaping output root rejected
- scenario_id/title/agent_id never used as raw filesystem paths
- manifest cannot list files outside root
- unexpected files fail manifest verification
- duplicate manifest entries rejected
- writes use canonical resolved path checks

### 14. Add replay/human-review artifacts

Severity: MEDIUM-HIGH

Before HTML replay, v0 still needs replay-friendly text/data.

Add:

```text
replay_timeline.jsonl
```

or:

```text
timeline.md
```

Each row should include:

- sequence/index
- event_id
- actor_id
- event_type
- human_summary
- source_refs
- candidate_refs
- evidence_refs
- authority_claim_refs
- authority_effect
- grants_authority
- status: social_only / candidate_only / blocked_authority_claim / evaluator_finding

Also rename `final_summary.md` to `run_report.md` or `final_run_report.md` to avoid implying final authority.

Reports should always include:

- “Authority Status: No authority granted”
- “Candidate outputs are non-authoritative”
- blocked authority claims with source links
- evidence table
- open human review questions
- how to verify this run
- files and hashes
- limitations

### 15. Tighten nomenclature and namespaces

Severity: MEDIUM

Avoid event names that imply authority or blur evaluator/protocol layers.

Recommended namespaces:

- workspace.*
- extraction.*
- evidence.*
- evaluator.*
- authority_fixture.*
- authority_protocol.* reserved for future real authority transitions

Rename:

- authority.claim.detected -> evaluator.authority_claim.detected
- authority.claim.blocked -> evaluator.authority_claim.blocked
- evidence.receipt.recorded -> evidence.receipt.observed or evidence.receipt.candidate_recorded, unless verified

Treat forbidden substrings as v0 non-authority namespace hygiene only, not global future restrictions.

### 16. Add CI/package setup earlier

Severity: MEDIUM

Add early:

- `pyproject.toml`
- Python version declaration
- `python3 -m compileall authority_workspace`
- `python3 -m unittest discover -s tests -v`
- `python3 -m json.tool` for all JSON scenario/schema files
- one deterministic CLI smoke into a temp output dir
- no-dependencies check if stdlib-first remains important

## Council synthesis

The plan’s conceptual core is sound. The main required change is to move from “block known fixtures” to “measure authority claims across raw and derived state with explicit ground truth, traceability, and replay.”

The most important implementation invariant should be:

> Every authority-relevant claim must be traceable from raw social input through candidate extraction, evidence references, evaluator findings, report output, and final authority state. No sanitization, summary, receipt, or audit artifact may erase or upgrade that claim.

## Recommended immediate action

Patch `docs/plans/0001-authority-aware-agent-workspace-v0.md` before coding.

Minimum patch set:

1. research design + measurement contract
2. canonical event envelope
3. artifact contract table
4. authority-state artifact
5. raw-claim detector contract
6. evidence/source-ref schema
7. context exposure logging
8. revised task sequence
9. report/replay requirements
10. positive-control decision: either no synthetic authority in v0, or explicit synthetic fixture semantics
