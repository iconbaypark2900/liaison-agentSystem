# Spark Agent System

A local-first, human-in-the-loop agentic engineering control plane for coordinating coding agents, local Ollama models, governed remote endpoint usage, research workers, validation profiles, and project workflows.

## Purpose

This repo manages the control plane for a controlled engineering department:

- local model routing
- capability-based remote routing
- context bundle generation
- human approval gates
- remote endpoint dry-runs
- research-worker dry-runs
- validation profiles
- task state inspection
- event and budget logging

## Current Status

Completed phases:

- Phase 1 — Control-plane registries and policies
- Phase 2 — Read-only inspection commands
- Phase 3 — Context bundle generation
- Phase 4 — Capability-based remote request skeleton
- Phase 5 — Research-worker / ML-Intern skeleton
- Phase 6 — Safe domain validation profiles
- Phase 7 — Conductor hardening
- Phase 7B — Context hygiene
- Phase 8A — NIM remote dry-run payload builder

## Core Command

```bash
spark-flow
```

## Documentation

- [Architecture](docs/architecture.md) — control plane vs runtime and directory map
- [Operating model](docs/operating_model.md) — human-in-the-loop, approvals, audit paths
- [Command reference](docs/command_reference.md) — `spark-flow` subcommands
- [Phase index](docs/phases/phase_index.md) — milestone tags

## Runtime Rule

Do not commit runtime state:

* `.spark-flow/`
* `logs/`
* API keys
* `.env`
* temporary task outputs
