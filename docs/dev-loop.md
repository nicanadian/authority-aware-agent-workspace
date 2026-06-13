# Development Loop

This repo uses a sequential dynamic frontier loop to implement `docs/plans/0001-authority-aware-agent-workspace-v0.md`.

## Loop rules

1. Work through plan tasks in order.
2. Exactly one task is in progress at a time.
3. Use strict TDD for code tasks:
   - write failing test first;
   - run it and confirm the expected failure;
   - implement minimal code;
   - run the targeted test;
   - run the broader suite/checks.
4. After each task, run a review gate:
   - spec compliance review;
   - quality/safety review when code or schemas changed.
5. If tests or reviewers reveal a blocking gap, add it as an immediate subtask before continuing.
6. If a useful but non-blocking follow-up appears, append it to the tail of the queue.
7. Do not start live-model functionality until the deterministic v0 acceptance criteria are green.
8. Keep generated run roots ignored unless deliberately force-added as curated examples.

## Standard verification commands

Use the commands that are valid for the current stage. By the end of v0, all must pass:

```bash
python3.11 -c 'import sys; assert sys.version_info >= (3, 11), sys.version'
python3.11 -m unittest discover -s tests -v
python3.11 -m compileall authority_workspace
find schemas scenarios -name '*.json' -print0 | xargs -0 -n1 python3.11 -m json.tool >/dev/null
python3.11 -m authority_workspace.cli run scenarios/fixtures/side_channel_approval.json --out .tmp-cli-smoke
python3.11 -m authority_workspace.cli evaluate .tmp-cli-smoke
```

Before commits:

```bash
git diff --check
python3.11 -m unittest discover -s tests -v
python3.11 -m compileall authority_workspace
```

## Task queue

Source of truth: `docs/plans/0001-authority-aware-agent-workspace-v0.md`, section `Revised implementation tasks`.

1. Add package scaffold and pyproject
2. Implement canonical event envelope
3. Add contracts and schema docs
4. Add scenario loader and one side-channel fixture
5. Implement safe artifact writer
6. Implement minimal runner: raw events + manifest only
7. Implement raw-claim detector
8. Implement evaluator for side-channel approval only
9. Integrate evaluator into runner
10. Add candidate state and evidence-linked projections
11. Add remaining fixtures one at a time
12. Add context exposure evaluator checks
13. Add replay timeline and Markdown report generator
14. Add CLI
15. Add protocol docs
16. Add CI

## Acceptance criteria

The loop is complete when the v0 acceptance criteria in the project plan are met and the repo is clean after commit/push.
