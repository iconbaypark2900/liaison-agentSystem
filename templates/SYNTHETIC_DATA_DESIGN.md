# Synthetic data design: <task-id>

## Dataset objective

What behavior, failure mode, or benchmark should this dataset improve or measure?

## Target use and prohibited uses

- Target use:
- Prohibited uses:

## Source seed policy

- Source type: scratch / logs / traces / documents / tickets / seed examples
- Redaction requirements:
- Lineage fields:

## Record schema

| Field | Type | Source | Constraints | Example |
|-------|------|--------|-------------|---------|

## Field dependencies

- `field_b` depends on `field_a` because ...

## Sampler plan

| Sampler | Values or distribution | Purpose |
|---------|------------------------|---------|

## Generation prompts

```text
Prompt template for generated field(s).
```

## Batch plan

- Preview size:
- Generation batch size:
- Maximum records before review:

## Validation checks

- Row-level checks:
- Dataset-level checks:
- Manual review sample size:

## Quality risks

- Hallucination risk:
- Label inconsistency risk:
- Leakage risk:
- Bias/coverage risk:

## Promotion path

```text
design -> preview batch -> validation report -> approved dataset artifact -> eval/fine-tune/flywheel use
```
