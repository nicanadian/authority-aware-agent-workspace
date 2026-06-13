# Vision: Authority-Aware Agent Workspaces

## Problem

Most multi-agent systems collapse several different things into one conversational stream:

- brainstorming
- claims
- summaries
- evidence
- proposed decisions
- approvals
- execution permissions
- audit records

That collapse creates authority-laundering risk. A plausible sentence like “everyone agreed,” “legal is done,” or “the deployment is approved” can become operationally dangerous if downstream agents treat it as authorization.

The danger is not only that agents hallucinate. The danger is that social text becomes a state transition.

## Thesis

Useful agent collaboration requires an explicit separation between:

1. social discourse;
2. candidate state extracted from discourse;
3. evidence and receipts;
4. protocol-valid decisions;
5. executable authority.

The workspace should let agents and humans remain socially fluent while the canonical state machine remains strict.

## Design principles

### 1. Conversation can propose state, but cannot authorize state

Messages, DMs, summaries, and channel membership are social context only. They can trigger extraction or review, but they cannot approve, delegate, spend, merge, deploy, publish, or close blockers.

### 2. Candidate state is useful but non-authoritative

Extracted proposals, blockers, tasks, charter slots, artifact patches, and summaries are reviewable candidate objects. They are not binding decisions.

### 3. Authority is scoped and explicit

A valid authority transition must name:

- principal
- action
- target
- scope
- expiry/revocation condition
- evidence/receipt
- protocol rule satisfied
- responsible human or institution, when required

### 4. Auditability proves existence, not legitimacy

A tamper-evident audit log proves that a record existed in an order. It does not prove that the record was semantically correct or authorized.

### 5. Context is an experimental treatment

Raw transcript, digest-only context, typed handoff, evidence-only context, and poisoned context should be configurable and measured separately.

### 6. Artifact quality and protocol validity are separate

A group can produce a useful artifact while failing authority discipline. A group can preserve authority boundaries while producing a weak artifact. Report both.

## Endgame

A workbench and eventually a product substrate where teams can run many AI agents in messy collaborative spaces, but every authority-relevant transition is explainable, evidence-linked, replayable, and permission-checked.
