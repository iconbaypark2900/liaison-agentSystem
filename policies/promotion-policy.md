# Promotion Policy

## Purpose

Define how model, endpoint, research, and validation outputs become trusted project artifacts.

## Promotion path

```text
outbox -> approved -> validated -> integrated -> committed
```

## Meanings

- `outbox`: raw model/research output, not trusted.
- `approved`: human reviewed and approved for possible use.
- `validated`: deterministic checks or scientific validation passed.
- `integrated`: local implementation agent applied the approved artifact.
- `committed`: Git recorded the final source of truth.

## Rules

- Endpoint outputs are read-only until approved.
- ML-Intern outputs are sandbox-only until approved and validated.
- NVIDIA Ising outputs are advisory until approved.
- No QPU/hardware action is promoted without explicit human approval.
- No publishing to Hugging Face or external registries without explicit human approval.
