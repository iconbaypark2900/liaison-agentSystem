---
name: synthetic-data-designer
description: Design high-quality domain-specific synthetic datasets from scratch, seed examples, logs, traces, or task specs for evaluation, fine-tuning, RAG, tool-use, and data-flywheel workflows. Use when creating dataset schemas, sampler plans, prompt/column dependencies, validation checks, or synthetic data generation reports; inspired by NeMo Data Designer but not dependent on NVIDIA services.
---

# Synthetic Data Designer Skill

## Purpose

Create a reproducible synthetic dataset design before generating data. Use this for:

- evaluation sets for agents, RAG systems, tools, and workflows
- fine-tuning or preference-data candidates
- data-flywheel curation from logs/traces into reusable examples
- seed expansion, scenario coverage, edge-case generation, and negative examples
- schema-first synthetic records with dependent fields

Treat NeMo Data Designer as the reference pattern: separate dataset configuration from execution, model each output field explicitly, manage dependencies between fields, generate in bounded batches, and validate generated rows against the intended specification.

## Workflow

1. Define the dataset objective.
   - Name the downstream use: eval, fine-tune, prompt test, RAG benchmark, tool-call regression, or flywheel training candidate.
   - Identify what failure mode or capability the dataset should measure or improve.

2. Define the record schema.
   - List each column/field, type, allowed values, and examples.
   - Mark generated fields, sampled fields, copied seed fields, labels, and derived fields.
   - State dependencies, such as `answer` depends on `question` and `source_context`.

3. Define source and seed policy.
   - Record whether data comes from scratch, logs, traces, documents, tickets, tasks, or curated seed examples.
   - Redact secrets and sensitive user data before generation.
   - Keep lineage from seed/source to generated row where possible.

4. Plan samplers and generators.
   - Use samplers for controlled variation: persona, domain, difficulty, language, product, scenario, tool, error type, or label.
   - Use LLM generators for text fields that need realistic composition.
   - Keep generation prompts constrained and column-specific.

5. Plan validation before scale.
   - Define row-level checks: required fields, enum membership, JSON validity, length bounds, label consistency, citation/source support, and safety filters.
   - Define dataset-level checks: class balance, coverage, duplicates, leakage, difficulty distribution, and regression coverage.

6. Generate in small batches first.
   - Start with a preview batch.
   - Inspect sample records manually.
   - Revise schema, prompts, samplers, and validators before larger generation.

7. Write a promotion report.
   - Summarize the design, generation settings, validation results, known caveats, and allowed use.
   - Attach it to Spark Flow outbox and require approval before training, evaluation gating, or route/deploy changes.

## Required Output Sections

When producing a synthetic data design or review, include:

- Dataset objective
- Target use and prohibited uses
- Source/seed policy
- Record schema
- Field dependencies
- Sampler plan
- Generation prompts or prompt templates
- Batch plan
- Validation checks
- Quality risks
- Promotion path

## Spark Flow Integration

For a governed dataset task:

```bash
spark-flow attach data_flywheel --file SYNTHETIC_DATA_DESIGN.md --title "Synthetic data design"
spark-flow observe data-designer --file SYNTHETIC_DATA_VALIDATION.md
spark-flow evaluate "Synthetic data design is ready for preview generation" --rubric synthetic_data --score <0-5>
spark-flow approve-artifact <artifact.md> --note "Approved for bounded synthetic data preview"
```

For data flywheels, link generated datasets to `FLYWHEEL_REPORT.md`, `TRACEABILITY_REPORT.md`, `SCORES.md`, `APPROVALS.md`, and `DECISIONS.md`.

## Guardrails

- Do not generate or preserve secrets, credentials, private user data, or regulated data without explicit approved handling.
- Synthetic data is not automatically truthful; validate factual, citation, and label fields.
- Do not use generated data for model training or routing decisions until its intended use, validation, and approval are recorded.
- Keep train/eval/holdout splits separate to avoid leakage.
- Prefer small preview batches before large generation.

## Review Checklist

- Does the dataset objective map to a concrete model or agent behavior?
- Are schema fields typed and constrained?
- Are dependent fields generated in a safe order?
- Are seed/source lineage and redaction rules clear?
- Are validation checks executable or at least deterministic?
- Does the report state what the dataset must not be used for?
- Is there an approval gate before training, eval gating, or deployment changes?
