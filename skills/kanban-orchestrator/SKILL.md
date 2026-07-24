---
name: kanban-orchestrator
description: Manage card lifecycle and coordinate multi-agent work across a Kanban board using spark-flow task primitives.
---

# Kanban Orchestrator Skill

## Purpose

Keep multi-agent work visible and moving on a Kanban board. Route cards to the right agent, track blockers, and close tasks cleanly.

## Rules

- Every piece of work must have a spark-flow task with a phase (PLAN, BUILD, TEST, PATCH, REVIEW, CLOSE).
- Cards move forward, never backwards, unless explicitly escalated.
- Blockers must be logged to the outbox within 15 minutes of discovery.
- No card stays In Progress without an active agent or human assignee.
- Completed phases require an approved artifact before the next phase starts.

## Phases

| Phase  | Owner     | Input          | Output              |
|--------|-----------|----------------|---------------------|
| PLAN   | claude    | task spec      | PROJECT_SPEC.md     |
| BUILD  | hermes    | PROJECT_SPEC   | implementation diff |
| TEST   | hermes    | diff           | test results        |
| PATCH  | codex     | failures       | fix diff            |
| REVIEW | claude    | diff + tests   | review.md           |
| CLOSE  | liaison   | review         | closeout record     |

## Steps

1. `liaison init <task-name>` — create the spark-flow task.
2. Assign the PLAN phase to claude; attach the spec on completion.
3. `liaison attach hermes --phase BUILD` — hermes implements.
4. `liaison attach hermes --phase TEST` — hermes runs tests.
5. If tests fail: `liaison attach codex --phase PATCH`.
6. `liaison attach claude --phase REVIEW` — review diff.
7. `liaison close-task` — after review approval.

## Output

- Updated board state (phase → agent → artifact)
- Blocker log if any phase stalls
- Closeout record in spark-flow outbox

## Guardrails

- Do not move a card to CLOSE without an approved artifact for each phase.
- Do not skip TEST; at minimum note "no tests required" with a justification.
- Do not assign multiple agents to the same phase of the same card simultaneously.
