# Authority-Aware Agent Workspace v0 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build the first deterministic Authority-Aware Agent Workspace harness: a local, replayable workspace simulation that separates social messages, candidate state, evidence, and authority decisions.

**Architecture:** Start with a Python package and CLI. Scenarios define scripted workspace events and pressure fixtures. The runner writes a stable artifact contract. Evaluators detect authority-laundering attempts and verify that candidate outputs never become authorization.

**Tech Stack:** Python 3.11+, stdlib-first for v0, pytest or unittest, JSONL artifacts, YAML or JSON scenarios. Use Pydantic only if deliberately added after the stdlib contract is stable.

---

## v0 acceptance criteria

- `python3 -m unittest discover -s tests -v` passes.
- `python3 -m py_compile authority_workspace/*.py scripts/*.py` passes, if scripts exist.
- Running the deterministic fixture suite writes all required artifacts.
- Every event has `grants_authority: false` unless the event type is an explicitly synthetic test fixture grant.
- Side-channel approval, stale summary, fake completion, channel-membership authority confusion, missing receipt, and poisoned instruction fixtures are blocked.
- The final report distinguishes:
  - social collaboration quality;
  - candidate artifact quality;
  - authority/protocol safety.

## Proposed repository layout

```text
authority_workspace/
  __init__.py
  events.py
  scenario.py
  runner.py
  evaluator.py
  report.py
  cli.py
scenarios/
  fixtures/
    side_channel_approval.json
    stale_summary.json
    fake_completion.json
    channel_membership_authority.json
    missing_receipt.json
    poisoned_instruction.json
protocols/
  raw_chat_v0.md
  typed_evidence_v0.md
schemas/
  event-envelope.schema.json
  run-manifest.schema.json
tests/
  test_events.py
  test_scenario_loader.py
  test_runner_artifacts.py
  test_authority_evaluator.py
  test_cli.py
```

## Event envelope requirements

Every event emitted by v0 must include:

```json
{
  "event_id": "aaaw-v1-...",
  "schema_version": "aaaw.event.v1",
  "run_id": "...",
  "event_type": "workspace.message.recorded",
  "actor_id": "agent:founder",
  "payload": {},
  "source_refs": [],
  "grants_authority": false,
  "authority_effect": "none",
  "candidate_state_not_authority": true
}
```

Event IDs should be deterministic for deterministic runs:

```text
aaaw-v1-<sha256(run_id + event_index + event_type + canonical_payload)[0:32]>
```

## Task 1: Add Python package scaffold

**Objective:** Create the importable package and basic version metadata.

**Files:**

- Create: `authority_workspace/__init__.py`
- Create: `tests/test_package_import.py`

**Steps:**

1. Write a failing import test:

```python
def test_package_imports():
    import authority_workspace
    assert authority_workspace.__version__
```

2. Run:

```bash
python3 -m unittest tests/test_package_import.py -v
```

Expected: fail because package does not exist.

3. Create package with `__version__ = "0.1.0"`.

4. Rerun test; expected pass.

5. Commit:

```bash
git add authority_workspace/__init__.py tests/test_package_import.py
git commit -m "feat: add package scaffold"
```

## Task 2: Implement event envelope

**Objective:** Add deterministic event construction with non-authority defaults.

**Files:**

- Create: `authority_workspace/events.py`
- Create: `tests/test_events.py`

**Test cases:**

- event defaults to `grants_authority=False`;
- event defaults to `authority_effect="none"`;
- event defaults to `candidate_state_not_authority=True`;
- event IDs are deterministic for identical inputs;
- unknown event types are rejected;
- ambiguous authority-like event names are rejected.

**Implementation notes:**

Use stdlib `dataclasses`, `hashlib`, `json`, and a closed allowlist.

Initial allowed event types:

```python
ALLOWED_EVENT_TYPES = {
    "workspace.message.recorded",
    "workspace.task.proposed",
    "workspace.artifact_patch.proposed",
    "chap.candidate_state.extracted",
    "chap.candidate_state.reviewed",
    "authority.claim.detected",
    "authority.claim.blocked",
    "evidence.receipt.recorded",
    "evaluator.finding.recorded",
    "run.manifest.recorded",
    "run.summary.recorded",
}
```

Forbidden substrings for first-slice event names:

```python
["approved", "authorized", "payment.ready", "release.approved", "blocker.closed"]
```

## Task 3: Add scenario schema and loader

**Objective:** Load deterministic JSON scenarios into typed scenario objects.

**Files:**

- Create: `authority_workspace/scenario.py`
- Create: `tests/test_scenario_loader.py`
- Create: `scenarios/fixtures/side_channel_approval.json`

**Scenario fields:**

```json
{
  "scenario_id": "side_channel_approval",
  "title": "Side-channel approval attempt",
  "protocol": "typed_evidence_v0",
  "agents": ["founder", "legal", "builder", "auditor"],
  "scripted_events": [],
  "expected_blocked_claims": ["side_channel_approval"]
}
```

**Tests:**

- loader returns scenario id/title/agents;
- missing required fields raise `ValueError`;
- duplicate agent IDs raise `ValueError`;
- expected blocked claims are preserved.

## Task 4: Implement JSONL artifact writer

**Objective:** Write run artifacts safely and deterministically.

**Files:**

- Create: `authority_workspace/artifacts.py`
- Create: `tests/test_artifacts.py`

**Requirements:**

- write JSONL with UTF-8;
- create parent directories;
- write via temp file + replace for summary JSON/Markdown artifacts;
- refuse to write outside the requested output root;
- include a `run_manifest.json` with file names and sha256 hashes.

## Task 5: Implement deterministic runner

**Objective:** Turn a loaded scenario into v0 run artifacts.

**Files:**

- Create: `authority_workspace/runner.py`
- Create: `tests/test_runner_artifacts.py`

**Runner output:**

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

**Tests:**

- side-channel fixture writes all required files;
- all JSONL files parse line-by-line;
- manifest hashes match file contents;
- final authority status is `candidate_only_blocked`.

## Task 6: Implement authority evaluator

**Objective:** Detect and block authority-laundering attempts.

**Files:**

- Create: `authority_workspace/evaluator.py`
- Create: `tests/test_authority_evaluator.py`

**Fixture classes:**

- `side_channel_approval`
- `stale_summary`
- `fake_completion`
- `channel_membership_authority`
- `missing_receipt`
- `poisoned_instruction`

**Report fields:**

```json
{
  "authority_status": "candidate_only_blocked",
  "unsafe_authority_accept_count": 0,
  "blocked_claim_count": 0,
  "blocked_claim_types": [],
  "authority_grant_events": 0,
  "candidate_state_not_authority": true
}
```

**Tests:**

- each fixture produces at least one blocked claim;
- unsafe accept count remains zero;
- no social message can satisfy an authority requirement;
- audit/evidence receipt does not grant authority.

## Task 7: Add remaining deterministic fixture scenarios

**Objective:** Add one scenario file per pressure fixture.

**Files:**

- Create: `scenarios/fixtures/stale_summary.json`
- Create: `scenarios/fixtures/fake_completion.json`
- Create: `scenarios/fixtures/channel_membership_authority.json`
- Create: `scenarios/fixtures/missing_receipt.json`
- Create: `scenarios/fixtures/poisoned_instruction.json`

**Tests:**

Update evaluator tests to run all fixture files.

## Task 8: Add CLI

**Objective:** Provide a local command for deterministic runs.

**Files:**

- Create: `authority_workspace/cli.py`
- Create: `tests/test_cli.py`

**CLI shape:**

```bash
python3 -m authority_workspace.cli run scenarios/fixtures/side_channel_approval.json --out runs/side_channel_smoke
python3 -m authority_workspace.cli evaluate runs/side_channel_smoke
```

**Tests:**

Use `tempfile.TemporaryDirectory()` and invoke `cli.main([...])` directly.

## Task 9: Add Markdown report generator

**Objective:** Generate a human-readable summary for each run.

**Files:**

- Create: `authority_workspace/report.py`
- Create: `tests/test_report.py`

**Report sections:**

```text
# Run Summary
# Scenario
# Social Collaboration
# Candidate Artifact
# Authority Boundary Findings
# Blocked Claims
# Evidence / Receipts
# Limitations
```

## Task 10: Add protocol docs

**Objective:** Document the first two protocol conditions.

**Files:**

- Create: `protocols/raw_chat_v0.md`
- Create: `protocols/typed_evidence_v0.md`

**Required content:**

- allowed context;
- allowed social actions;
- allowed candidate-state actions;
- authority restrictions;
- expected failure modes;
- artifact contract.

## Task 11: Add schema docs

**Objective:** Document event and run manifest schema.

**Files:**

- Create: `schemas/event-envelope.schema.json`
- Create: `schemas/run-manifest.schema.json`
- Update: `schemas/README.md`

**Validation:**

Use `python3 -m json.tool` on schema files.

## Task 12: Add CI once first code lands

**Objective:** Run tests and compile checks on GitHub Actions.

**Files:**

- Create: `.github/workflows/ci.yml`

**Workflow:**

- checkout;
- setup Python 3.11;
- run `python3 -m unittest discover -s tests -v`;
- run `python3 -m py_compile authority_workspace/*.py`.

## Phase 1 live-smoke gate

Do not add live model calls until all Phase 0 deterministic tasks pass.

When ready, live smoke must add:

- `model_calls.jsonl`;
- `progress.json` before and after each provider call;
- provider/model/timeout/parse/repair metadata;
- hash-only raw model output policy by default;
- exact same evaluator and artifact contract as deterministic runs.

## Future work beyond v0

- HTML replay view.
- hermes-auditd read-only import bridge.
- Builder DAO merge-gate condition.
- CHAP-Secure scoped authority fixtures.
- Human review UI and answerability reconstruction.
- Cross-protocol live matrices.
