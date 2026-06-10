# Closed Feedback Policy

## Purpose

Keep agent-system aligned with objectives while improving from observations,
failures, and validation results.

## Loop

```text
objective -> knowledge/context -> reasoning/handoff -> action/report -> observation -> evaluation -> learning -> improvement -> updated knowledge
```

## Rules

- Every task must have an objective.
- Context snapshots are preferred over chat history.
- Raw agent output stays in `outbox/` until approved.
- Evaluations must state rubric, score, and pass/fail status.
- Failed evaluations should create a learning or improvement item.
- Closeout must mention unresolved risks and next actions.
