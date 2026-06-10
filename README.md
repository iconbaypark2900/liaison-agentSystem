# Liaison

Local-first, human-in-the-loop **Liaison control plane** for coordinating AI-assisted
engineering across repos, hub agents, research workers, validation profiles,
and approval gates.

Liaison is the intermediary between **hub agents** and **registered projects**.

## Purpose

This repo (`$LIAISON_ROOT`) manages the durable control plane for work on this Spark:

- task briefs and context snapshots
- raw hub agent reports in `outbox/`
- human approvals and rejections
- decisions and handoffs
- validation summaries
- closeout records
- local model and capability registries
- project phase routing (`registry/phase_routing.yaml`)

Operator docs: `~/spark/docs/local-agents/liaison/` (see also [docs/spark-local-guides.md](docs/spark-local-guides.md)).

The **integrated operator model** describes one filesystem and JSON state across the web command center, Textual TUI, and terminal panes: executors run in the terminal, Liaison governs on disk, and both UIs mirror `liaison command-center --json`. Full guide: [docs/integrated-operator-model.md](docs/integrated-operator-model.md).

## Core Command

```bash
liaison
```

(`spark-flow` remains a backward-compatible alias.)

## Look (browse control plane)

```bash
liaison look              # hub agents, projects, open tasks, memory/debrief
liaison look --refresh    # regenerate task/project indices first
liaison command-center    # Textual TUI (alias: liaison tui; see requirements.txt)
liaison command-center --json   # JSON state for web dashboard / CI
```

Install TUI deps: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`

## Web command center (local)

TypeScript dashboard under `dashboard/web/` — sidebar routes, gate strip, projects/hub/ops panels. See [dashboard/README.md](dashboard/README.md).

```bash
cd dashboard/web && cp .env.local.example .env.local && npm install && npm run dev
```

## Default Reporter Flow

Run from the repo being worked on:

```bash
liaison init task-001 "One focused goal"
liaison snapshot --show
liaison attach hermes --text "Implementation report..."
liaison approve-artifact <outbox-file>
liaison decision "Approved approach X"
liaison validate --profile python
liaison close-task --summary "Task complete"
```

## Optional Executor Flow

The legacy phase lane remains available when Flow should own execution:

```bash
liaison start plan
liaison approve plan
liaison start build
```

## Documentation

- [Integrated operator model](docs/integrated-operator-model.md)
- [Operator quick reference](docs/operator-quick-reference.md)
- [Operator upgrades roadmap](docs/operator-upgrades-roadmap.md)
- [Architecture](docs/architecture.md)
- [Operating model](docs/operating_model.md)
- [Command reference](docs/command_reference.md)
- [Phase index](docs/phases/phase_index.md)

## Runtime Rule

Do not commit runtime state:

* `.spark-flow/`
* `logs/`
* API keys
* `.env`
* temporary task outputs
