# Project Specification — Spark Agent System

## System Goal

Build a governed local-first agent orchestration system that coordinates local coding agents, hosted endpoint models, research workers, validation profiles, and human approval gates.

## Design Principles

1. Local-first by default.
2. Human approval before remote execution.
3. Remote outputs are read-only until approved.
4. Context bundles are the source of truth, not chat history.
5. Runtime state is not source code.
6. Every important action should create an auditable artifact.
7. Real endpoint/model execution must be behind budget and policy gates.

## Main Components

* `bin/spark-flow`: CLI conductor
* `config/`: routing, provider, worker, budget, skill, and validation registries
* `policies/`: governance rules
* `checks/`: validation scripts
* `workflows/`: workflow definitions
* `skills/`: skill descriptions
* `templates/`: reusable task/project templates
* `departments/`: department/agent role definitions

## Execution Lanes

### Local Lane

Used for coding, patching, review, and deterministic validation.

### Remote Endpoint Lane

Flow:

```text
request-remote -> approve-remote -> remote-run --stub/--real --dry-run
```

### Research Worker Lane

Flow:

```text
request-research -> approve-research -> research-run --stub
```
