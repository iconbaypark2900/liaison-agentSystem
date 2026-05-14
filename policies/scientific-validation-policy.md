# Scientific Validation Policy

## Purpose

Ensure scientific, ML, quantum, and experimental claims are reproducible and validated.

## Required artifacts

- experiment.yaml
- metrics.yaml
- results_schema.json
- experiment_log.jsonl
- run_report.md
- baseline comparison
- seed policy or documented stochasticity

## Rules

- Claims must map to metrics.
- Experiment logs are append-only.
- Baselines must be recorded.
- Statistical uncertainty must be recorded when relevant.
- Failed runs must be logged, not hidden.
