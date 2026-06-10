# Operating model — Liaison (reporter-first control plane)

The operating rule is:

```text
Hub agents do the work. Liaison preserves context, records reports, asks for approval, and prevents handoff loss.
```

## Reporter flow

```text
init -> snapshot -> attach -> approve/reject artifact -> decision -> validate -> close-task
```

- `init` creates the task filesystem.
- `snapshot` records repo context so chat history is not the source of truth.
- `attach` stores Hermes, QCA, ML Intern, Unsloth, Codex, OpenCode, Claude, or
  human reports in `outbox/`.
- `approve-artifact` promotes useful output to `approved/`.
- `reject-artifact` preserves rejected output and the reason.
- `decision` appends durable operator decisions.
- `validate` records deterministic checks.
- `close-task` compiles the final closeout.

## Phase executor compatibility

`start`, `approve`, and `reject` for plan/build/patch/review/close remain
available. Use them only when Spark Flow should own execution for the branch.

## Committed vs runtime

Commit control-plane definitions: `registry/`, `config/`, `policies/`,
`checks/`, `workflows/`, `skills/`, `templates/`, `departments/`, `bin/`, and
`docs/`.

Do not commit `.spark-flow/`, `logs/`, `.env`, secrets, or temporary outputs.

## Promotion path

```text
outbox -> approved -> validated -> integrated -> committed
```


## Antifragile loop

Use these commands when a task needs adaptation and self-correction:

```bash
liaison objective "Define success" --metric "Observable success criteria"
liaison observe hermes --text "What happened"
liaison evaluate "Assessment against objective" --rubric alignment --score 4
liaison learn "What future tasks should do differently"
liaison improve "Concrete follow-up action" --priority high --owner hermes
liaison feedback-cycle --show
```

A failed evaluation is useful only if it becomes a learning or improvement item.
That is the antifragile behavior: stress produces better future behavior.


## Gates and cross-task memory

Before closeout, run deterministic checks:

```bash
liaison drift-check --show
liaison gate --show
```

When a task teaches a reusable lesson, promote it:

```bash
liaison promote-learning --tags "repo,topic"
liaison memory-report
```

Promoted memory is intentionally reviewed before commit; `memory/*.learning.md`
is ignored by default.


## Scoring and dashboard cadence

Use scoring before final gate review when a task has produced artifacts:

```bash
liaison score-artifacts --show --fail-under 3
liaison gate --show
```

Use cross-task reports during daily startup or closeout review:

```bash
liaison trend-report --show
liaison index-tasks --show
liaison dashboard --show
```

Generated dashboard JSON and Markdown are ignored by default except `dashboard/README.md`; review before committing any generated summary.


## Data flywheel workflow

Use `data_flywheel` when the agent needs to improve from real traffic rather than a one-off task. The loop is:

```text
traffic/logs -> curated examples -> candidate experiments -> evaluator scorecard -> approved routing recommendation -> monitoring -> learning
```

Start with `liaison init`, attach a `FLYWHEEL_REPORT.md` artifact, run `score-artifacts`, and record an explicit decision before changing model routes, prompts, tool policies, or deployment targets.


For orchestration-heavy flywheels, attach `FLYWHEEL_ORCHESTRATION_PLAN.md` before experiments. It should name traffic ingestion, data partitions, scheduled jobs, service dependencies, API/CI integration points, retries, and rollback handling. The Iguazio/MLRun pattern is useful as a guide for what the orchestrator should track, but Spark keeps those controls file-backed and approval-gated.


For traceability-heavy flywheels, attach `TRACEABILITY_REPORT.md` before evaluation. It should capture agent steps, tool/model calls, retrieved context, evaluator runs, and latency/cost/safety metrics. W&B Weave is a useful reference implementation for tracing and evaluation, but Spark keeps the approval artifact local and reviewable.


Use `synthetic-data-designer` before generating or promoting synthetic data. The skill should produce `SYNTHETIC_DATA_DESIGN.md`, a preview/validation report, and an approval path before the data is used for training, evaluation gates, or data-flywheel routing decisions.


## Debrief and choice loop

When a repo has been selected but the next build direction is unclear, bootstrap memory and browse state:

```bash
liaison look --refresh
liaison memory-init --show
liaison debrief --show
liaison control-panel --interactive
# or: liaison command-center   # multi-panel TUI across hub, projects, tasks, memory
liaison choose 1 --show
```

The debrief produces 4-6 options: one recommended path, nearby alternatives, and an expansive option that remains tied to the recommended baseline. The interactive panel lets the operator inspect an option, choose it, refresh recommendations, or quit. `choose` records the selected path, the agents involved, the step-by-step plan, and the pivot rule in repo memory.

## Starting without a selected task

When there is no concrete task selection, run:

```bash
liaison discover-projects --show
liaison plan-next --show
liaison dashboard --show
```

This inspects registered repos, detects project-specific build/test commands, and produces a prioritized local backlog in `dashboard/NEXT_WORK.md`. The backlog is deterministic and file-backed; it gives the next agent a concrete place to start.
