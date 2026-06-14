# Schemas

Schema definitions for Authority-Aware Agent Workspace artifacts.

Current schemas:

- `event-envelope.schema.json` encodes canonical event envelopes and source refs. Every v0 non-synthetic event has `grants_authority false`, `authority_effect none`, and `candidate_state_not_authority true`. The v0.1 `synthetic_authority_controls` fixture is the only sandbox exception: `authority.synthetic_grant.recorded` events may use `grants_authority true` with `authority_effect synthetic_authority_fixture`, but only as fixture data for evaluator controls.
- `run-manifest.schema.json` encodes run metadata, scenario hash, fixture type, protocol, context mode, seed, runner version, artifact schema version, and artifact hashes/counts.
- `scenario.schema.json` encodes asynchronous workspace scenario fixtures: agents, channels, DM threads, tasks, artifact drafts, handoffs, and scripted events. Synthetic grant scripted events are reserved for the `synthetic_authority_controls` fixture.
- `authority-evaluator-report.schema.json` encodes treatment variables, outcome metrics, authority status, counts, source-linked findings, and tightly shaped synthetic authority-control findings.

No-authority invariant: v0 schemas document and enforce that candidate state, social claims, reports, receipts, manifests, audit records, and non-synthetic event envelopes are not authority. The v0.1 synthetic authority sandbox is deliberately scoped to `synthetic_authority_controls`: accepted synthetic grants set `synthetic_sandbox_only true` and `real_world_authority false`; they measure control behavior and never imply real-world authority. Evaluator reports keep real authority grant counts fixed to zero and `authority_state_changed_by_invalid_claim` fixed false.

Source refs are provenance links and must include `ref_type`, `ref_id`, and `relationship`. Evaluator findings must include source event IDs and human explanations so blocked authority claims remain reviewable rather than just counted.
