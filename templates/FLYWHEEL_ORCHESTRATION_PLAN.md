# Flywheel orchestration plan: <task-id>

## Objective

Describe the continuous optimization loop being orchestrated.

## Traffic ingestion

- Source systems:
- Log store/query:
- Collection cadence:
- Retention and redaction:

## Data partitioning

- Training/ICL set:
- Evaluation set:
- Holdout/regression set:
- Sampling policy:

## Job schedule

| Job | Trigger | Inputs | Outputs | Owner | Retry/rollback |
|-----|---------|--------|---------|-------|----------------|
| collect | manual/scheduled | logs | curated examples | data_flywheel | |
| evaluate | manual/scheduled | candidates + eval set | scorecard | data_flywheel | |
| tune | approved/manual | train set + base model | adapter/model artifact | unsloth/ml_intern | |

## Service dependencies

- NIM proxy or local route:
- Evaluator service:
- Fine-tuning/customizer service:
- Datastore/entity registry:
- CI/CD integration point:

## API surface

- Submit run:
- Check status:
- Fetch scorecard:
- Approve recommendation:

## Failure handling

- Retry policy:
- Stop conditions:
- Rollback route:
- Human escalation:

## Approval gates

No scheduled job may alter model routing, prompt policy, tool policy, or deployment without an approved scorecard and recorded decision.
