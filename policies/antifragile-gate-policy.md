# Antifragile Gate Policy

## Purpose

Prevent task closeout when the feedback loop is incomplete.

## Required before closeout

- objective recorded
- context snapshotted
- at least one observation
- at least one evaluation
- approved or rejected artifact decision
- failed evaluations create a learning
- learnings create an improvement
- feedback-cycle generated

## Commands

```bash
spark-flow gate --show
spark-flow drift-check --show
spark-flow promote-learning --tags "topic"
```
