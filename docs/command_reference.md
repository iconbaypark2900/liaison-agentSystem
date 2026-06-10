# Command reference — `liaison`

The primary CLI entrypoint is **`bin/liaison`** (`python3`). **`bin/spark-flow`**
remains a backward-compatible alias. Both require a subcommand.

```bash
bin/liaison --help
bin/liaison <subcommand> --help
```

## Project onboarding and phase

Lifecycle (tracking): `register → assess → classify`. Maturity (product): `unassessed → prototype → alpha → beta → mvp`.
Task lifecycle (per slice): `init → snapshot → attach → approve-artifact → decision → validate → gate → close-task`.

| Command | Arguments | Description |
|---------|-----------|-------------|
| `register-project` | `path`, optional `--name`, `--profile`, `--role`, `--phase` | Adds the repo to `registry/repos.yaml` and runs `memory-init`. Lifecycle becomes `registered` and maturity `unassessed` (Prototype is not assumed). `--phase` classifies immediately. State in `.spark-flow/memory/project_phase.json` + `PROJECT_PHASE.md`. |
| `assess-project` | optional `--show` | Inspects repo evidence (tests, CI, deploy docs, toolchain, prior closeouts), writes `ASSESSMENT.md` with a recommended phase, and sets lifecycle to `assessed`. |
| `project-intake` | optional `--project NAME`, `--json`, `--write`, `--show` | Read-only intake score: brief, task hygiene, lifecycle/assessment, runnable signals. Writes `INTAKE_REPORT.md` with `--write`. Included in `command-center --json` when a project is focused. |
| `plan-project` | optional `--project NAME`, `--json`, `--write`, `--show` | Portfolio operating plan from `registry/project_plans.yaml` (workflow, pattern, research/engineering gates, backlog, optional `reporter_auto_advance`). Merges intake when repo path exists. `--write` fills `PROJECT_OPERATING_PLAN.md` under `.spark-flow/memory/`. Included in `command-center --json` as `project_plan` when focused. |
| `record-build` | `--agent`, `--action`, `--outcome`, optional `--notes` | Appends a structured step to the current task `BUILD_TRACE.md` (build corpus). See [build-corpus-and-custom-agent.md](build-corpus-and-custom-agent.md). |
| `export-agent-recipe` | `--from-project` / `--project NAME`, optional `--task-id`, `--recipe-id`, `--write`, `--json`, `--show` | Aggregates task traces, learnings, and approved artifacts into `templates/AGENT_RECIPE.md` output; `--write` stores under `registry/recipes/` and indexes `registry/agent_recipes.yaml`. |
| `project-phase` | `show` \| `classify [--phase <name>` \| `--from-assessment]` \| `set <phase>` \| `advance`, optional `--reason`, `--note`, `--yes` | Shows lifecycle + maturity; `classify` records the assessed maturity (lifecycle → classified); `advance` (classified only) moves to the next phase from `registry/phase_routing.yaml`. |
| `start-pattern` | optional `pattern_id`, `--task-id`, `--description`, `--list` | Scaffolds a task `BRIEF.md` with the agent chain, expected outbox artifacts, and handoff checklist from `registry/hub_skills.yaml` `project_agent_patterns`. |

## Execution bridge

| Command | Arguments | Description |
|---------|-----------|-------------|
| `terminal-session` | `list` \| `prune` \| `register` \| `complete` | Registry at `memory/terminal_sessions.json`. `register` accepts `--project`, `--task-id`, `--pattern`. `complete` records executor outcome into task artifacts via the bridge. |
| `observe-session` | `start` (like register) \| `complete` | Operator-facing bridge: `complete` writes `OBSERVATIONS.md`, `events.jsonl`, and on failure `EVALUATIONS.md` + `LEARNINGS.md`. See [execution-bridge.md](execution-bridge.md). |
| `venture-queue` | `list` \| `add` \| `next` \| `mark-running` \| `mark-done` \| `cancel` | Lightweight queue at `memory/venture_queue.json`; `next` respects `registry/workstation_profile.yaml` capacity (no auto-spawn in v1). |

Helper: `bin/liaison-session-done <agent> <exit-code> [log-file]` — reads `LIAISON_PROJECT` / `LIAISON_TASK` or repo `operator_session.json`.

## Reporter mode (primary path)

| Command | Arguments | Description |
|---------|-----------|-------------|
| `init` | `task_id`, `description`, optional `--workflow NAME` | Creates `.spark-flow/`, current task state, phase folders, and reporter files (`BRIEF.md`, `CONTEXT.md`, `APPROVALS.md`, `DECISIONS.md`, `HANDOFFS.md`, `VALIDATION.md`, `CLOSEOUT.md`). `--workflow` tags the task with a workflow. |
| `snapshot` | optional `--show` | Refreshes durable repo/task context in `CONTEXT.md` and writes a reporter manifest. |
| `attach` | `agent`, exactly one of `--file PATH` or `--text TEXT`, optional `--title TITLE` | Stores a report from Hermes, QCA, ML Intern, Unsloth, Codex, OpenCode, Claude, or a human in `outbox/`. |
| `approve-artifact` | `artifact`, optional `--note NOTE` | Copies an outbox artifact to `approved/` and appends `APPROVALS.md`. |
| `reject-artifact` | `artifact`, `reason` | Copies an outbox artifact to `rejected/` and records the rejection in `APPROVALS.md`. |
| `decision` | `text` | Appends a timestamped durable decision to `DECISIONS.md`. |
| `validate` | optional `--profile NAME` | Runs the validation profile script; without `--profile` uses the repo's registered `default_profile`. Honors the `script:` field in `validation_profiles.yaml`; `none` is a no-op. |
| `close-task` | optional `--summary TEXT`, `--require-gate` | Compiles `CLOSEOUT.md` and marks the task complete. Blocks on a failing `gate`/validation when the project phase requires validation (Alpha+) or `--require-gate` is set; MVP adds production-readiness checks. |
| `reporter-step` | `show` \| `set <step>` \| `advance`, optional `--task-id`, `--complete`, `--force` | Reporter checklist step machine. Persists `reporter_step_state.json` under the task dir (`current_step_id`, `completed_steps`, `updated_at`). Steps: init → snapshot → attach → approve → validate → close. `advance` requires current step complete (probe or `--complete`) unless `--force`. Exposed in command-center JSON as `reporter_step_state`. |
| `registry` | `repos`\|`agents`\|`skills`\|`workflows`\|`artifact-contracts`\|`phase-routing`\|`hub-skills`\|`rolodex`\|`evaluations` | Prints central registry YAML from `registry/`. |

## Closed feedback loop

| Command | Arguments | Description |
|---------|-----------|-------------|
| `objective` | `text`, optional `--metric TEXT` | Appends task objective and success metric to `OBJECTIVES.md`. |
| `observe` | `source`, exactly one of `--file PATH` or `--text TEXT`, optional `--title TITLE` | Records observations from agents, tools, users, tests, or repo state in `OBSERVATIONS.md`. |
| `evaluate` | `text`, `--score 0-5`, optional `--rubric NAME`, `--pass-score N` | Records rubric-based evaluation in `EVALUATIONS.md`. |
| `learn` | `text` | Appends durable lessons to `LEARNINGS.md`. |
| `improve` | `text`, optional `--priority`, `--owner` | Appends concrete improvement actions to `IMPROVEMENTS.md`. |
| `feedback-cycle` | optional `--show` | Compiles objectives, context, observations, evaluations, learnings, improvements, approvals, and validation into `FEEDBACK_LOOP.md`. |
| `gate` | optional `--show`, `--production` | Runs deterministic closeout gates and writes `GATE_REPORT.md`; exits nonzero on failure. `--production` (auto at MVP phase) adds deploy/rollback, secret-hygiene, and validation checks, plus closed-feedback success conditions. |
| `drift-check` | optional `--show`, `--fail-on-findings` | Checks for objective/approval/decision drift and writes `DRIFT_CHECK.md`. |
| `promote-learning` | optional `--tags TEXT` | Promotes task learnings into `$LIAISON_ROOT/memory/`. |
| `memory-report` | optional `--limit N` | Lists promoted learnings. |
| `score-artifacts` | optional `--show`, `--fail-under N` | Scores current task artifacts in `outbox/`, `approved/`, and `rejected/`; writes `SCORES.md`, `scores.json`, and appends an evaluation summary. |

## Repo memory, debrief, and recommendation control panel

| Command | Arguments | Description |
|---------|-----------|-------------|
| `memory-init` | optional `--show` | Initializes per-repo `.spark-flow/memory/` with Markdown memory files, `tasks/backlog.yaml`, `debriefs/`, and `memory.sqlite`. |
| `debrief` | optional `--show`, `--limit N` | Loads project files, repo memory, git state, and detected commands; writes a timestamped debrief under `debriefs/`, ranks 4-6 next options, and refreshes a structured `current_state.md` (phase, built/todo, next action) rather than dumping the raw debrief. |
| `recommend` | optional `--show`, `--limit N` | Prints the latest ranked options from repo memory, including recommended, adjacent, and expansive paths. |
| `choose` | `option`, optional `--reason TEXT`, `--show`, `--init`, `--task-id ID` | Records a selected recommendation into `.spark-flow/memory/CHOICE.md`, `decisions.md`, and SQLite. `--init` scaffolds the next task from the chosen option. |
| `control-panel` | optional `--refresh`, `--interactive` | Debrief recommendations for the current repo; interactive mode supports inspect, choose, refresh, and quit. |
| `look` | optional `--refresh`, `--interactive` | **Browse Liaison state:** hub agents, registered projects, open tasks (task phase), memory/debrief summary. |
| `command-center` | optional `--refresh`, `--once`, `--json`, `--project NAME` | **Textual command center TUI** — all hub agents, skills/recommendations/handoff chains, kanban, linked project matrix, handoffs/debriefs, engineering metrics. `--once` prints ASCII snapshot (no Textual). `--json` prints machine-readable state for the web dashboard and CI. `--project` scopes kanban/handoffs to one registered repo key. |
| `tui` | optional `--refresh`, `--once`, `--json`, `--project` | Alias for `command-center`. |

## Trends and dashboard

| Command | Arguments | Description |
|---------|-----------|-------------|
| `trend-report` | optional `--show`, `--limit N` | Reads promoted learnings from `memory/*.learning.md`; writes `memory/TREND_REPORT.md` and `memory/trends.json`. |
| `index-tasks` | optional `--repo PATH`, `--show` | Indexes `.spark-flow/tasks/*` from registered repos plus an optional repo; writes `dashboard/TASK_INDEX.md` and `dashboard/tasks.json`. |
| `dashboard` | optional `--show` | Writes `dashboard/DASHBOARD.md` and `dashboard/dashboard.json` with task, gate, score, memory, trend, project discovery, and next-work summary. |
| `discover-projects` | optional `--repo PATH`, `--show` | Scans registered repos plus an optional repo for project markers and inferred setup/build/test/validate commands; writes `dashboard/PROJECTS.md` and `dashboard/projects.json`. |
| `plan-next` | optional `--repo PATH`, `--limit N`, `--show`, `--init`, `--task-id ID` | Generates `dashboard/NEXT_WORK.md` and `dashboard/next_work.json` from open tasks, git status, project markers, and detected commands. `--init` scaffolds a task from the top item. |

## Phase executor mode (optional compatibility path)

| Command | Arguments | Description |
|---------|-----------|-------------|
| `start` | `phase` (`plan`\|`build`\|`patch`\|`review`\|`close`) | Requires `ollama`, `curl`, and the routed agent binary; writes `prompts/<phase>.md`, launches agent via `ollama launch`. |
| `approve` | `phase` | Copies `outbox/<phase>.md` to `approved/`; advances phase/handoff. |
| `reject` | `phase`, `reason` | Writes `feedback/<phase>.md`; resets approval for that phase. |
| `context` | `phase`, optional `--show` | Generates phase context bundle under `context/`. |

## Diagnostics

| Command | Description |
|---------|-------------|
| `status` | Prints current task state, approvals, git short status, and loaded Ollama models. |
| `doctor` | Prints PATH resolution for `ollama`, `curl`, `git`, `claude`, `opencode`, `codex`; probes Ollama API. |
| `stop` | Stops loaded Ollama models from the built-in model map. |
| `events` | Streams task `events.jsonl`. |
| `check-state` | Verifies current task files and state. |

## Routing, workflows, validation

| Command | Arguments | Description |
|---------|-----------|-------------|
| `routes` | — | Lists local/remote/quantum model route blocks. |
| `route` | `query` | Scores configured routes against a free-text query. |
| `workflows` | — | Lists workflow YAMLs under `$LIAISON_ROOT/workflows`. |
| `validate` | `--profile NAME` | Runs `checks/<NAME>.sh`; writes validation summary to task outbox when a task exists. |
| `validations` | — | Lists validation profiles. |
| `capabilities` | — | Prints capability blocks. |
| `capability` | `name` | Prints one capability. |
| `skills` | — | Prints skill resolution config. |
| `skills-for` | `workflow_name`, `phase` | Lists skills for a workflow phase; data-flywheel phases include `synthetic-data-designer`. |

## Remote and research governance

| Command | Arguments | Description |
|---------|-----------|-------------|
| `remote-capabilities` | — | Lists remote-allowed capabilities. |
| `request-remote` | `capability`, `request_text` | Writes pending remote request. |
| `approve-remote` | `capability` | Records remote approval. |
| `remote-run` | `capability`, `--stub` or `--real --dry-run` | Writes remote stub/dry-run artifacts and logs. |
| `research-workers` | — | Lists research workers. |
| `request-research` | `worker_name`, `request_text` | Writes pending research request. |
| `approve-research` | `worker_name` | Records research approval. |
| `research-run` | `worker_name --stub` | Writes research stub output and logs. |

## Web dashboard — browser execution (Track E1)

Internal subcommands used by `dashboard/web` API routes (not operator-facing CLI):

| Subcommand | Arguments | Description |
|------------|-----------|-------------|
| `run-allowlisted` | `--cmd CMD`, optional `--project NAME` | Validates and runs allowlisted liaison writes; JSON `{ok, output, cmd}`. Audit: `memory/browser_liaison_audit.jsonl`. |
| `reporter-step-advance-browser` | `--project NAME`, optional `--task-id ID` | Opt-in reporter-step advance when `reporter_auto_advance: true` in `registry/project_plans.yaml`. Never uses `--force`. JSON on stdout. |

**HTTP routes**

| Route | Body | Allowlist / gates |
|-------|------|-------------------|
| `POST /api/liaison/run` | `{ cmd, project?, task? }` | `validate`, `approve-artifact`, `close-task`, `start-pattern` (+ readonly). Confirm in browser. |
| `POST /api/liaison/reporter-step/advance` | `{ project, task? }` | Requires `project_plan.reporter_auto_advance`; current reporter step complete; approve outbox cleared. |

**Phase controls panel** (`PhaseControlsPanel.tsx`): **Run next workflow step** / per-row **Run** on `suggested_workflow_commands` when intake soft-ready (E1.1 gates). **Advance reporter step** when project opts in (E1.3). Hard refresh (`?refresh=1`) after success.

## Paths

- Control plane: `$LIAISON_ROOT` (Liaison)
- Per-repo runtime: `<repo>/.spark-flow/tasks/<task-id>/`
- Runtime logs: `$LIAISON_ROOT/logs/`

Do not commit `.spark-flow/`, `logs/`, `.env`, secrets, or temporary outputs.
