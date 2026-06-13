# Scenarios

Scenarios define deterministic or live workspace runs.

The first scenario family is `fixtures/`, a deterministic pressure suite for authority-boundary failures:

- side-channel approval
- stale summary
- fake completion
- channel-membership authority confusion
- missing receipt
- poisoned instruction

Scenario outputs are candidate-only unless an explicit future scoped-authority fixture says otherwise.
