# Post-CI Project Council Review

Date: 2026-06-14
Repo: `/Users/nicanadian-macmini/repos/authority-aware-agent-workspace`
Scope: project state after Tasks 10-16 plus Task 15.5 council blocker fixes.

## Current state verified before review

- Branch: `main`, ahead of `origin/main` by 9 commits.
- Untracked file present: `docs/research-ideas.md`.
- Verification:
  - `python3.11 -m unittest discover -s tests -v`: 146 tests passed.
  - `python3.11 -m compileall authority_workspace tests`: passed.
  - `python3.11 -m json.tool` over all repo JSON files excluding `.git`: passed.
  - Deterministic CLI smoke run + evaluate: passed.
  - `git diff --check`: passed.
- Size snapshot:
  - Python: 28 files / 5,210 lines.
  - Markdown: 17 files / 2,855 lines.
  - JSON: 15 files / 1,331 lines.
  - YAML: 1 file / 50 lines.

## Council panel

1. Distributed Systems / Protocol Architect
2. AI Safety / Context-Contamination Researcher
3. Security / Evidence-Integrity Reviewer
4. Standards / Documentation Editor
5. Product / Platform Implementer
6. Skeptical External Critic

## Executive verdict

The project is in good shape as an internal deterministic v0 authority-boundary harness. The code, tests, CLI, reports, protocol docs, evidence-integrity hardening, and CI now form a coherent baseline.

The defensible current claim is narrow:

> Under curated deterministic fixtures, this harness produces source-linked non-authoritative artifacts and blocks detector-caught raw social authority claims from mutating authority state.

The project is not yet public-ready as evidence of live-agent safety, model resistance to context poisoning, or full authority-awareness. It has no live model calls, no positive authority path, and only fixture-scoped deterministic claim detection.

## Consensus strengths

- Deterministic v0 baseline is green and CI-backed.
- Event/artifact contracts are coherent for internal v0.
- Artifact writer has strong path and atomic-write hygiene.
- Candidate state and reports preserve non-authority semantics.
- Public CLI `evaluate` was materially hardened after the previous council:
  - clears stale derived outputs before failure paths;
  - validates manifest shape and provenance;
  - anchors `scenario_sha256` to trusted fixtures;
  - regenerates expected initial/candidate artifacts and byte-compares before scoring.
- Reports now include deterministic-v0 limitation language.
- Protocol docs are stronger than the front-door docs and are contract-tested.
- CI runs unit tests, compileall, JSON syntax validation, and CLI smoke without secrets or network calls beyond GitHub actions setup.

## Consensus blockers

None for an internal deterministic v0 CI freeze.

## Consensus near-blockers / public-readiness blockers

### 1. Front-door docs are stale

`README.md` still says “Planning scaffold only.” `docs/roadmap.md` still describes Phase 0 as current and includes stale `aaaw` / YAML examples. `scenarios/README.md` omits newer fixtures.

Recommended fix:
- Rewrite README with current status, Python 3.11 requirement, quickstart, CLI examples, artifact overview, fixture list, and limitations.
- Update roadmap status and examples.
- Update scenario/protocol README inventories.

### 2. Current result is authority-denying, not full authority-aware

There is no positive authority path or synthetic valid authority fixture. Metrics such as false accept/reject are not yet oracle-derived in the strong sense.

Recommended fix:
- Add a v0.1 positive-control formal authority fixture with scoped grants, mismatched-scope negatives, and oracle-derived metrics.

### 3. Context modes are labels/placeholders

`context_exposure.jsonl` is useful for deterministic provenance, but `raw_transcript`, `digest_only`, `redacted_raw`, `attribution_blind`, etc. are not yet real prompt/context transformations. Byte fields are deterministic placeholders.

Recommended fix:
- Before live smoke, materialize actual context surfaces, hashes, included/omitted refs, and prompt/context byte counts per mode.

### 4. Raw-event-only claim extraction leaves laundering surfaces

The evaluator currently scans raw workspace event payloads. Derived artifacts are not yet fully scanned as possible authority-laundering surfaces.

Recommended fix:
- Scan or explicitly scope out `tasks.jsonl`, `artifact_patches.jsonl`, `candidate_state.jsonl`, `candidate_state_reviews.jsonl`, Markdown reports, and future model outputs.

### 5. Detector is fixture-scoped and heuristic

Regex detector coverage is enough for current fixtures, but not robust against many obvious paraphrases or obfuscations.

Recommended fix:
- Add adversarial detector fixtures for paraphrases, quote traps, emoji/reaction approvals, Unicode/homoglyphs, multilingual variants, and negative controls.

### 6. Schema coverage is incomplete for the artifact surface

Core schemas exist, but many generated JSON/JSONL artifacts do not have standalone JSON Schemas.

Recommended fix:
- Either add schemas for all machine-consumed artifacts or document exactly which artifacts are schema-backed vs contract-tested but schema-less in v0.

### 7. API boundary ambiguity

The CLI `evaluate` path is hardened. The lower-level `authority_workspace.evaluator.evaluate_run()` remains callable and does not enforce the full trusted-fixture byte-compare gate.

Recommended fix:
- Document `evaluate_run()` as low-level/internal, or move the strict validation gate into a shared public evaluation function used by both CLI and library callers.

### 8. Packaging/source-tree assumption

CLI trusted fixture discovery is source-tree-relative. There is no console script or package-data story for installed distributions.

Recommended fix:
- Decide whether this is source-checkout-only or installable. If installable, add package data/resources, console script, and install smoke tests.

### 9. CI is deterministic but not release-grade

CI is good for v0, but it does not yet include all-fixture CLI runs, schema validation of generated artifacts, README command smoke, packaging smoke, or supply-chain SHA pinning.

Recommended fix:
- Add those incrementally after docs/package policy is settled.

### 10. Workspace hygiene

`docs/research-ideas.md` is untracked. Main is ahead of origin by 9 commits.

Recommended fix:
- Decide whether to commit, move, or ignore the untracked note before handoff/push.
- Push once docs/public-readiness hygiene is complete.

## Recommended next task sequence

1. Documentation alignment pass:
   - README current status + quickstart + limitations.
   - Roadmap current status and next phases.
   - Scenario/protocol README inventory updates.
   - Add post-fix addendum to previous council review or cross-link this review.

2. Repo hygiene:
   - Decide fate of `docs/research-ideas.md`.
   - Push 9 commits once docs are clean.

3. Library/API boundary hardening:
   - Make strict trusted evaluation a shared/public path or document `evaluate_run()` as non-security-boundary internal.

4. Artifact/schema hardening:
   - Add artifact schemas or schema coverage docs/tests.
   - Add generated artifact validation to CI.

5. CLI/product ergonomics:
   - Add better help text, success summary, output/report paths, `--run-id`, and output overwrite policy.
   - Consider `aaaw` console script.

6. Packaging policy:
   - Source checkout only vs installable package.
   - If installable, add package data/resources and install smoke.

7. v0.1 research credibility:
   - Add positive-control scoped authority fixture.
   - Expand detector adversarial coverage.
   - Scan derived artifacts for laundering.
   - Implement real context-mode materialization before live calls.

8. Live-smoke seam design:
   - Add `model_calls.jsonl`, prompt/context hashes, parse/repair metadata, model output scanning, and failure-before-success semantics before any provider call.

## Bottom line

Proceeding to public-ish docs/handoff cleanup is the right next move. Proceeding directly to live model experiments would be premature unless the live step is explicitly framed as plumbing-only, because the current harness does not yet measure model resistance or full authority discrimination.
