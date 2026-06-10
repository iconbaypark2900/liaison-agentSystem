# Project Specification — Spark Agent System

## System Goal

Build a governed local-first work filesystem for human-approved AI work. The
system coordinates agents by preserving task context, reports, approvals,
decisions, validation, handoffs, and closeout records across repos and tools.

## Design Principles

1. Local-first by default.
2. Agents do the work; agent-system records, gates, and preserves context.
3. Context bundles and task artifacts are the source of truth, not chat history.
4. Human approval promotes raw output into trusted artifacts.
5. Runtime state is not source code.
6. Every important action should create an auditable artifact.
7. Real endpoint/model execution must be behind budget and policy gates.

## Main Components

* `bin/spark-flow`: CLI conductor and reporter-mode task filesystem tool
* `registry/`: repo, agent, skill, workflow, and artifact-contract catalogs
* `config/`: routing, provider, worker, budget, skill, and validation registries
* `policies/`: governance rules
* `checks/`: validation scripts
* `workflows/`: workflow definitions
* `skills/`: skill descriptions
* `templates/`: reusable task, report, approval, handoff, and closeout templates
* `departments/`: department/agent role definitions

## Reporter Mode

Default flow:

```text
init -> snapshot -> attach -> approve/reject artifact -> decision -> validate -> close-task
```

Agents such as Hermes, QCA, ML Intern, Unsloth Studio, Codex, OpenCode, and
Claude produce reports or work outputs. `spark-flow` stores those outputs in
`outbox/`, promotes reviewed artifacts to `approved/`, records decisions, and
builds a durable closeout.

## Optional Execution Lanes

### Phase Executor Lane

Existing phase execution remains available:

```text
start plan/build/patch/review/close -> approve/reject phase
```

Use this only when Spark Flow should own the execution lane.

### Remote Endpoint Lane

```text
request-remote -> approve-remote -> remote-run --stub/--real --dry-run
```

### Research Worker Lane

```text
request-research -> approve-research -> research-run --stub
```


## Closed Feedback Architecture

The system implements a closed loop:

```text
objective -> knowledge/context -> reasoning/handoff -> action/report -> observation -> evaluation -> learning -> improvement -> updated knowledge
```

New task artifacts support this loop: `OBJECTIVES.md`, `OBSERVATIONS.md`,
`EVALUATIONS.md`, `LEARNINGS.md`, `IMPROVEMENTS.md`, and `FEEDBACK_LOOP.md`.

Antifragility means failures and surprises are not hidden. They are converted
into observations, evaluated, distilled into learnings, and turned into concrete
improvement actions.
