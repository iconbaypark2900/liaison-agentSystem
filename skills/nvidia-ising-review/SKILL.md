---
name: nvidia-ising-review
description: Review NVIDIA Ising, CUDA-Q, calibration, decoding, or quantum validation workflows.
---

# NVIDIA Ising Review Skill

## Purpose

Review quantum workflows involving NVIDIA Ising, CUDA-Q, QPU calibration, or quantum error-correction decoding.

## Required checks

1. Is this calibration, decoding, simulation, benchmarking, or orchestration?
2. Are input data, plots, and schemas defined?
3. Are backend, shots, seeds, and run IDs explicit?
4. Are benchmark_plan.yaml and results_schema.json present?
5. Is experiment_log.jsonl append-only?
6. Are QPU/hardware actions human-approved?
7. Are Ising outputs advisory, not automatically applied?

## Output

- Verdict: approve / approve with changes / reject
- Quantum-specific risks
- Missing configs or schemas
- Validation commands
- Minimal patch instructions
