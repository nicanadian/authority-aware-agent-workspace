# Protocols

Protocols describe workspace/control conditions to compare. Current v0 protocol docs define deterministic, candidate-only conditions for the local harness.

## Current v0 protocol index

- [`raw_chat_v0`](raw_chat_v0.md): messy social-context condition. Raw channel and DM text is available as evidence for analysis, but social claims, side-channel statements, summaries, membership facts, and instructions must not become authority.
- [`typed_evidence_v0`](typed_evidence_v0.md): typed candidate/evidence condition. Structured records improve traceability, but typed evidence, candidate records, receipts, reviews, and reports remain non-authoritative unless a future formal authority mechanism says otherwise.

Each protocol doc specifies:

- allowed context;
- allowed social actions;
- allowed candidate-state actions;
- authority restrictions;
- expected failure modes;
- required artifact contract;
- context exposure behavior.

## Current limitations

- v0 has no positive authority path. The safe result for current fixtures is blocked/candidate-only authority state.
- The evaluator currently extracts authority-like claims from `workspace_events.jsonl` raw event payloads. Typed candidate artifacts are evaluated for support, evidence linkage, and unsupported counts rather than treated as a separate authority-claim source.
- Context modes are explicit deterministic labels/placeholders in current fixtures, not a complete prompt/redaction pipeline.
- No live model protocol evidence exists yet; live model smoke tests are future work.

Protocol docs should continue to preserve the core invariant: candidate state is not authority.
