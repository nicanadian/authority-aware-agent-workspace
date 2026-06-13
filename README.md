# Authority-Aware Agent Workspaces

Authority-Aware Agent Workspaces is a research and prototyping project for multi-agent collaboration systems where social discussion, candidate state, evidence, and executable authority are kept deliberately separate.

The core thesis:

> Agent collaboration does not mainly need more chat. It needs explicit boundaries between social claims, candidate state, evidence, protocol-valid decisions, and actual authority.

This repository is the unification point for the research threads around CHAP/DAO governance, swarm control-plane ablations, async agent workspaces, context poisoning, typed handoffs, Builder DAO, and tamper-evident audit logs.

## What this project is

A research workbench for building and testing authority-aware collaboration protocols:

- Slack/Discord-style async agent workspaces
- typed event logs and replayable run artifacts
- candidate-state extraction from messy social discourse
- evidence-linked handoffs and receipts
- explicit authority ledgers and merge gates
- pressure fixtures for context poisoning, fake completion, stale summaries, and side-channel approval
- deterministic-first evaluators before broad live model runs
- replay/report artifacts that show who claimed what, what evidence existed, and which transitions were actually authorized

## What this project is not

- Not an autonomous company product yet.
- Not a DAO that grants real-world authority.
- Not a security claim that agents can govern safely.
- Not a generic chat app.

All generated decisions, blockers, candidate artifacts, and audit records are non-authoritative unless a future explicit authority layer validates a scoped transition.

## Core invariant

Social text is not authority.
Summaries are not authority.
Model output is not authority.
Audit records are not authority.
Candidate state is not authority.

Only protocol-valid, scoped, evidenced, permissioned transitions can mutate authoritative state.

## Planned first slice

The first implementation target is a local deterministic harness:

```text
scenario yaml/json
  -> async workspace event log
  -> candidate-state extractor
  -> authority-boundary evaluator
  -> report/replay artifacts
```

No live model calls are required for Phase 0. Live GPT-5.5/Codex smokes come only after deterministic fixtures and artifact contracts are stable.

## Repository map

```text
docs/
  vision.md
  architecture.md
  roadmap.md
  research-lineage.md
  plans/
    0001-authority-aware-agent-workspace-v0.md
schemas/
  README.md
scenarios/
  README.md
protocols/
  README.md
evaluators/
  README.md
runs/
  .gitkeep
```

## Current status

Planning scaffold only. The v0 implementation plan is in:

`docs/plans/0001-authority-aware-agent-workspace-v0.md`
