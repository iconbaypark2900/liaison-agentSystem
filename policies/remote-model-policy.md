# Remote Model Policy

## Purpose

Control hosted endpoint model usage.

## Rules

- Local-first by default.
- Remote calls require explicit human approval.
- Remote outputs are read-only.
- Remote outputs must be written to outbox.
- Remote outputs must be approved before handoff.
- Remote calls must be logged.
- Remote routes must use capabilities, not hardcoded model IDs, when used by workflows.
