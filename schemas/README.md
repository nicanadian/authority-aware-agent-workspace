# Schemas

Schema definitions for Authority-Aware Agent Workspace artifacts.

Current schemas:

- `event-envelope.schema.json` encodes canonical event envelopes and source refs. Every v0 event has `grants_authority false`, `authority_effect none`, and `candidate_state_not_authority true`.
- `run-manifest.schema.json` encodes run metadata, scenario hash, fixture type, protocol, context mode, seed, runner version, artifact schema version, and artifact hashes/counts.
- `scenario.schema.json` encodes asynchronous workspace scenario fixtures: agents, channels, DM threads, tasks, artifact drafts, handoffs, and scripted events.
- `authority-evaluator-report.schema.json` encodes treatment variables, outcome metrics, authority status, counts, and source-linked findings.

No-authority invariant: v0 schemas document and enforce that candidate state, findings, reports, receipts, manifests, and audit records are not authority. In event envelopes, `grants_authority false` and `authority_effect none` are fixed contract values; candidate state is explicitly non-authoritative. In evaluator reports, real and synthetic authority grant counts are fixed to zero and `authority_state_changed_by_invalid_claim` is fixed false.

Source refs are provenance links and must include `ref_type`, `ref_id`, and `relationship`. Evaluator findings must include source event IDs and human explanations so blocked authority claims remain reviewable rather than just counted.
