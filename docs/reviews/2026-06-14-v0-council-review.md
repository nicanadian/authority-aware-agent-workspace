# v0 Council Review — Tasks 10–15

Date: 2026-06-14
Repo: `/Users/nicanadian-macmini/repos/authority-aware-agent-workspace`
Scope: commits `origin/main..HEAD` after Task 9, covering Tasks 10–15:

- Task 10: candidate state and evidence-linked projections
- Task 11: remaining authority fixtures
- Task 12: context exposure evaluator checks
- Task 13: replay timeline and Markdown report generator
- Task 14: deterministic CLI
- Task 15: protocol docs

Controller validation before council:

- Branch: `main`, ahead of `origin/main` by 6 commits
- `python3.11 -m unittest discover -s tests -v`: 136 tests passed
- `python3.11 -m compileall authority_workspace tests`: passed
- `git diff --check`: passed
- Diff size: 24 files, 2242 insertions, 60 deletions

Panel participants chosen:

1. Distributed systems / protocol architect
2. AI safety / context-contamination researcher
3. Security / evidence-integrity reviewer
4. Standards / documentation editor
5. Product / platform implementer
6. Skeptical external critic

## Executive verdict

The council agrees the current v0 is a strong deterministic internal scaffold for a no-authority/candidate-only artifact pipeline. It is not yet public-ready as an interoperable protocol or as behavioral evidence of live model resistance.

Recommended path:

1. Fix evidence-integrity and metric correctness blockers before Task 16 CI.
2. Then add CI.
3. Then do a docs/onboarding/schema hardening patch.
4. Only after that start v0.1 positive controls or live-smoke work.

## Consensus strengths

- Deterministic core is solid:
  - canonical JSON writes
  - stable event IDs
  - repeatable runs
  - manifest hashes/byte counts/JSONL line counts
  - fast suite: 136 tests in under a second locally

- No-authority invariant is consistently represented:
  - `grants_authority: false`
  - `authority_effect: none`
  - `candidate_state_not_authority: true`
  - hard-blocked/candidate-only evaluator state

- Raw-event traceability is good for v0:
  - channel/DM projections link to `workspace_events.jsonl`
  - claims/findings carry source event IDs
  - replay timeline joins back to source event IDs

- Artifact hygiene is unusually good for a v0:
  - path traversal/symlink escape tests
  - stale evaluator/report output cleanup in normal evaluator/report paths
  - Markdown multiline injection tests
  - CLI manifest freshness regression

- Protocol docs are conceptually aligned with the no-authority goal and now list the full current artifact surface.

## Blocking or near-blocking issues before public draft

### 1. Incorrect report metric: `unsupported_candidate_state_count`

Multiple reviewers independently flagged this.

Current behavior appears to set top-level `unsupported_candidate_state_count` from total unsupported candidate objects, not unsupported candidate-state objects.

Observed mismatch reported by reviewers:

- `unsupported_candidate_object_count`: 3
- `unsupported_candidate_state_count`: 3
- `counts.unsupported_candidate_state_objects`: 2

Impact:

- Not an authority bypass.
- But it weakens evaluator-report fidelity and could mislead downstream metrics consumers.

Required fix:

- Wire `unsupported_candidate_state_count` to `unsupported_candidate_state_objects`.
- Add a regression asserting top-level value equals `counts.unsupported_candidate_state_objects`.

### 2. CLI `evaluate` can leave stale derived artifacts on early failure

Security review found that CLI `evaluate` rewrites pre-evaluation manifest metadata before `evaluate_run()` gets a chance to remove stale evaluator outputs.

If an input artifact is missing, `_rewrite_manifest()` raises first, leaving old derived outputs in place:

- `authority_claims.jsonl`
- `authority_state.json`
- `authority_evaluator_report.json`
- `evidence_manifest.json`
- `replay_timeline.jsonl`
- `candidate_artifact.md`
- `run_report.md`

Impact:

- Users or automation could consume stale success artifacts after a failed re-evaluation.

Required fix:

- Add CLI-level failure-after-success test.
- Ensure CLI `evaluate` clears or invalidates evaluator/report outputs before any early failure path that follows a previous success.

### 3. CLI `evaluate` trusts mutable manifest provenance fields

Security review found `evaluate` recomputes artifact hashes but preserves potentially forged manifest metadata such as:

- `scenario_id`
- `scenario_sha256`
- `fixture_type`
- `seed`
- extra unexpected fields

Manual probe reportedly changed `scenario_id` to `forged_scenario`; `evaluate` succeeded and final report/manifest used the forged value.

Impact:

- Evidence provenance weakness.
- Final manifest can violate schema if extra fields are preserved.

Required fix:

- Validate final manifest against the closed schema, or reconstruct provenance from a trusted source.
- At minimum, fail closed on unknown fields and on provenance fields that cannot be independently verified.
- Prefer storing enough scenario path/hash provenance to recompute scenario metadata, or label existing manifest provenance as trusted input and verify its schema/hash consistency.

### 4. Public docs/onboarding are stale

Docs reviewers and product reviewer flagged that the implementation has advanced beyond the front-door docs.

Current issues:

- `README.md` still says planning scaffold only.
- `docs/roadmap.md` uses stale phase/status language.
- `scenarios/README.md` omits newer fixtures.
- Some examples mention `aaaw` or YAML while current CLI is `python3 -m authority_workspace.cli` over JSON fixtures.
- CLI help is minimal.

Impact:

- Not a code correctness blocker.
- But it is a public-readiness blocker and will confuse new contributors.

Required fix:

- Update README with Python 3.11 requirement, quickstart, test command, CLI command, artifact overview, and current fixture list.
- Update scenarios/protocols/roadmap docs to match implementation.
- Clarify v0 has no positive authority path and no live-model evidence.

## Major scope limitations to state explicitly

### 1. v0 is authority-denying, not yet authority-aware

The skeptical critic’s strongest point: the evaluator has no positive authority path. It hard-blocks all authority-like claims and sets false accept/reject metrics to zero rather than computing them against an oracle.

This is acceptable for deterministic v0 if scoped honestly.

It does not prove the system can distinguish valid formal authority from invalid social/candidate claims.

Required wording:

- “v0 verifies deterministic non-authority artifact invariants only.”
- “v0 has no positive authority path.”
- “v0 does not prove live model resistance to poisoned context.”

### 2. Claim extraction scans raw workspace events only

Current detector/evaluator scans raw `workspace_events.jsonl` payloads. It does not scan all derived artifacts for authority laundering, despite the broader plan eventually wanting that surface.

Derived surfaces not yet scanned as claim sources:

- `tasks.jsonl`
- `artifact_patches.jsonl`
- `candidate_state.jsonl`
- `candidate_state_reviews.jsonl`
- `candidate_artifact.md`
- `run_report.md`
- future model output surfaces

This is documented in `typed_evidence_v0.md`, but should be repeated in README/report limitations.

### 3. Context modes are labels, not real treatment implementations yet

Current `context_exposure.jsonl` records deterministic visibility and placeholders:

- `prompt_bytes: 0`
- `context_bytes: 0`
- `deterministic_placeholder: true`

Modes such as `redacted_raw`, `digest_only`, and `attribution_blind` are accepted labels, not fully differentiated exposure transformations.

### 4. Detector coverage is narrow

The regex detector covers common phrases, but obvious paraphrases remain untested or unsupported:

- “LGTM”
- “ship it”
- “blessed”
- “+1 from owner”
- “legal is happy”
- emoji/reaction authority
- unicode/homoglyph variants
- multi-language variants
- quote attribution traps

This is fine for fixture-scoped v0, not for broad robustness claims.

## Recommended next patch set before CI

Before Task 16, fix the small correctness/security blockers so CI locks the right behavior:

1. Fix `unsupported_candidate_state_count` and add regression.
2. Fix CLI `evaluate` stale-output behavior on early failure and add regression.
3. Validate or reconstruct manifest provenance on CLI `evaluate`; at least reject unknown fields and forged provenance where possible.
4. Add/adjust docs/report limitation wording: deterministic v0 only, no live model resistance, no positive authority path.

Then Task 16 CI should run:

- `python3.11 -m unittest discover -s tests -v`
- `python3.11 -m compileall authority_workspace`
- JSON validation for schemas and scenarios
- deterministic CLI smoke into a temp directory
- `git diff --check` if practical

Important: use Python 3.11 explicitly. Local `python3` on this machine is Python 3.9.6 and fails on `tomllib`; pytest is not installed and should not be used unless added as a dependency.

## Recommended follow-on patch set after CI

1. Update README/roadmap/scenarios docs.
2. Add or document schemas for all JSON/JSONL artifacts, or explicitly state which artifacts are schema-less in v0.
3. Tighten `scenario.schema.json` nested shapes.
4. Add docs/tests defining candidate object vs candidate state terminology.
5. Add generated report sections for:
   - limitations
   - how to verify
   - files/hashes pointer to `run_manifest.json`
   - status explanation for `hard_blocked_candidate_only`
6. Add CLI ergonomics:
   - console script or documented module invocation only
   - `--run-id`
   - existing-output guard / `--force`
   - clearer `evaluate` help saying outputs are rewritten
   - print artifact/report paths and claim counts

## Future experiments suggested by council

- v0.1 positive-control authority fixture with scoped synthetic formal grant.
- Derived-artifact laundering tests: inject authority claims into candidate state, patches, reviews, typed evidence fields, and reports.
- Oracle-based metrics for false accepts/rejects rather than hard-coded zeros.
- Real context-mode transformations and byte counts.
- Poison-marker positive/negative corpus, including defensive statements that should not be marked as poison.
- Fixture-specific causal assertions:
  - stale summary freshness
  - missing receipt absence
  - channel membership vs role authority
  - overbroad delegation scope mismatch
- Future live smoke only after deterministic artifact/evidence gates are hardened.

## Final council recommendation

Do not move directly to Task 16 yet if the goal is to freeze a clean baseline in CI. First do a small “council blocker fix” task for:

1. report metric correctness,
2. CLI failed-evaluate stale artifacts,
3. manifest provenance/schema validation,
4. explicit deterministic-v0 limitation wording.

After that, proceed to CI.

If the goal is just internal iteration speed, Task 16 can be added now, but CI will lock in known evidence-integrity bugs and stale docs.
