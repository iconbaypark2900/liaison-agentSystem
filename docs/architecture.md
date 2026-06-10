# Architecture — Liaison

Liaison is the durable work filesystem and governance layer — intermediary
between hub agents and registered projects.

## Control plane vs runtime

| Layer | Location | Role |
|-------|----------|------|
| Control plane | `bin/`, `registry/`, `evaluations/`, `config/`, `policies/`, `checks/`, `workflows/`, `skills/`, `templates/`, `departments/`, `docs/` | Defines commands, catalogs, policies, validation, templates, and optional routes. |
| Runtime | `<repo>/.spark-flow/`, `logs/` | Per-task briefs, context, reports, approvals, rejections, decisions, handoffs, validation, closeout, and event logs. |

## Reporter-first task filesystem

Each task lives under `<repo>/.spark-flow/tasks/<task-id>/` and includes:

- `BRIEF.md`
- `CONTEXT.md`
- `APPROVALS.md`
- `DECISIONS.md`
- `HANDOFFS.md`
- `VALIDATION.md`
- `CLOSEOUT.md`
- `outbox/`, `approved/`, `rejected/`, `attachments/`

## Registries

`registry/` gives the filesystem a catalog:

- `repos.yaml`
- `agents.yaml`
- `skills.yaml`
- `workflows.yaml`
- `artifact_contracts.yaml`
- `phase_routing.yaml` — project phases (Prototype/Alpha/Beta/MVP) vs task phases

## Execution lanes

1. Reporter mode: agents do work elsewhere; `spark-flow` stores reports,
   approvals, decisions, and closeout.
2. Phase executor mode: `spark-flow start <phase>` launches the routed local CLI
   agent for plan/build/patch/review/close.
3. Remote/research governance: request, approve, run stub/dry-run, and log.


## Closed feedback loop

The loop is explicit and file-backed:

| Step | Artifact | Command |
|------|----------|---------|
| Objective | `OBJECTIVES.md` | `spark-flow objective` |
| Knowledge/context | `CONTEXT.md` | `spark-flow snapshot` |
| Reasoning/handoff | `HANDOFFS.md` | `spark-flow attach` / handoff notes |
| Action/report | `outbox/` | `spark-flow attach` |
| Observation | `OBSERVATIONS.md` | `spark-flow observe` |
| Evaluation | `EVALUATIONS.md` | `spark-flow evaluate` |
| Learning | `LEARNINGS.md` | `spark-flow learn` |
| Improvement | `IMPROVEMENTS.md` | `spark-flow improve` |
| Updated knowledge | `FEEDBACK_LOOP.md` | `spark-flow feedback-cycle` |

`evaluations/closed-feedback-loop.yaml` defines required files and success conditions.


## Antifragile gates

`gate` makes the feedback loop enforceable. It fails when objective, context,
observation, evaluation, artifact decision, learning/improvement, or feedback
cycle records are missing. `drift-check` detects obvious mismatch patterns such
as approved artifacts without decisions. `promote-learning` moves durable lessons
from per-repo task memory into `$LIAISON_ROOT/memory/`.


## Project context bootstrap

The recommendation layer is deliberately evidence-backed:

```text
Terminal UI / control panel
  -> project context loader
  -> repo memory store
  -> debrief and planner
  -> recommended next actions
```

Per-repo memory lives under `<repo>/.spark-flow/memory/` and starts with `project_brief.md`, `current_state.md`, `decisions.md`, `tasks/backlog.yaml`, `debriefs/`, and `memory.sqlite`. `debrief` loads those files plus README/package metadata/docs, git status/log, and detected project commands. `control-panel` and `recommend` only rank options from this evidence layer, so advice is tied to memory, repo files, or command output instead of chat history.

## Scoring, trends, and dashboard

`score-artifacts` adds deterministic 0-5 structure scores to each task via `SCORES.md` and `scores.json`. `trend-report` aggregates reviewed promoted learnings from `memory/*.learning.md` into recurring tags, phrases, owners, and source repos. `index-tasks` and `dashboard` create Markdown and JSON summaries under `dashboard/` so cross-repo state remains local-first and reviewable.


## Data flywheel agent

The `data_flywheel` agent profile adapts NVIDIA's enterprise data-flywheel pattern to Spark Flow's file-backed control plane: production traffic is captured as governed observations, curated into reviewable datasets, compared through candidate-model scorecards, and promoted only through approval and decision artifacts. Spark keeps the orchestration local-first; external NIM, NeMo, evaluator, or fine-tuning services remain optional governed integrations rather than default runtime dependencies. The Iguazio orchestration blueprint adds the scheduling/control-plane view: Spark records job manifests, data partitions, service dependencies, API touchpoints, retries, and rollback conditions before any continuous optimization is automated.


The W&B traceability blueprint adds the observability view: each flywheel recommendation should be explainable through traces of agent steps, tool calls, model calls, retrieved context, evaluator runs, latency, cost, and safety findings. Spark represents this as `TRACEABILITY_REPORT.md` and links it to evaluations, scores, approvals, and decisions.


## Synthetic data designer skill

`synthetic-data-designer` adapts the NeMo Data Designer pattern into a Spark skill. It designs schema-first synthetic datasets from scratch, seeds, logs, traces, or documents, records sampler and field-dependency plans, requires preview/validation before scale, and links approved datasets into evaluation, fine-tuning, RAG, or data-flywheel workflows.


## Project discovery and next-work planning

`discover-projects` scans registered repos for project markers such as `package.json`, `pyproject.toml`, `Makefile`, `Cargo.toml`, and `go.mod`, then infers setup, build, test, lint, typecheck, and validation commands. `plan-next` combines that discovery with open Spark Flow tasks and git status to generate a local next-work backlog without requiring the operator to pick a task first.

## See also

- [Integrated operator model](integrated-operator-model.md) — web, TUI, and terminal surfaces; hub groups; six-step choreography; trigger matrix
- [Operator quick reference](operator-quick-reference.md) — one-page tmux layout and copy commands
- [Operator upgrades roadmap](operator-upgrades-roadmap.md) — prioritized UI/UX items A–H
- [Dashboard README](../dashboard/README.md) — Next.js command center setup
