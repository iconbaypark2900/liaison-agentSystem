---
name: spark-flow-review
description: Review a spark-flow task after BUILD, TEST, or PATCH without editing source files.
---

# Spark Flow Review Skill

## Purpose

Review a completed spark-flow task before the human approves it.

## Rules

- Do not edit source files.
- Read AGENTS.md, PROJECT_SPEC.md, TASKS.md, DECISIONS.md.
- Read approved phase outputs under `.spark-flow/tasks/<task>/approved/`.
- Inspect git status and git diff.
- Verify implementation against acceptance criteria.
- Check tests, dependencies, security risks, and scope drift.
- Return approve / approve with changes / reject.
- Write the result to `.spark-flow/tasks/<task>/outbox/review.md`.

## Output

# REVIEW summary

## Verdict

approve | approve with changes | reject

## Findings

- ...

## Missing tests

- ...

## Minimal patch instructions

- ...

## Closeout instructions

- ...
