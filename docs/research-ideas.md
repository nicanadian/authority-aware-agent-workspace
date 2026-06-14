# Research ideas

## 2026-06-14 — olmo-eval-style workbench for authority/control-plane experiments

**Idea:** Spike Ai2's [`olmo-eval`](https://github.com/allenai/olmo-eval) as a possible backbone, or design reference, for repeated Ark/Chaos/DAO/swarm authority-boundary evaluations.

**Motivation:** Current experiments often produce bespoke reports for specific sweeps. An olmo-eval-style workbench could make repeated intervention/checkpoint/model comparisons more systematic by separating:

- **Task / scenario definition:** authority-boundary scenario, adversary family, pressure condition, context treatment.
- **Harness / runtime policy:** raw transcript vs digest, tool/no-tool, model provider, scaffold, sandbox, social-pressure loop.
- **Scoring:** authority grant, contract violation, unsafe claim support, usefulness, parseability, family-level risk.
- **Storage / analysis:** aggregate metrics plus per-instance predictions for paired comparisons across interventions.

**Why olmo-eval is interesting:**

- Clean task/suite/harness abstraction.
- Supports plain, tool-using, scaffolded, and sandboxed evaluation modes without rewriting task definitions.
- Stores aggregate and instance-level predictions.
- Includes pairwise comparison, standard error, and minimum-detectable-effect framing for “is this delta real or noise?”
- Has inspection tooling for instances, formatted prompts, token arrays, and model responses.

**Spike plan:**

1. Clone `allenai/olmo-eval` and run mock dry-runs / task inspection locally.
2. Wrap one existing authority experiment as a thin `ExternalEval` rather than rewriting the sim.
3. Start with DAO scenario suite or swarm control-plane ablation because they already have clear scenario IDs and per-instance outcomes.
4. Export per-instance records with stable IDs, family labels, pressure condition, context condition, and binary/graded scores.
5. Compare two interventions using olmo-eval's pairwise machinery: e.g. raw transcript vs hard-redacted digest, or baseline vs authored-patch guard.
6. Decide whether to adopt olmo-eval directly, borrow the schema/statistical analysis, or build a smaller compatible workbench.

**Cautions / design questions:**

- olmo-eval is young and likely shaped around Ai2 infrastructure such as Beaker/storage conventions.
- Authority scenarios are clustered; family-level dependence needs careful variance treatment.
- Safety and usefulness should remain separate axes, not collapsed into one leaderboard score.
- Scenario-family weighting and repeated seeds need explicit policy.
- The right first milestone is a thin wrapper and pairwise report, not a full migration.

**Success criterion:** A small spike can answer: “For the same scenario IDs, did intervention B actually improve authority-boundary behavior over intervention A, and where exactly did it regress?”
