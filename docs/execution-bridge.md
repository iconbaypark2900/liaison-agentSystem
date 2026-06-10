# Execution bridge

Connects **hub agents in terminal panes** to **Liaison governance** on disk so executor success and failure become observations, evaluations, and learnings — without Cursor as translator.

## Architecture

```text
Pane A (tmux)     Hermes / QCA / ML Intern — natural CLI environment
Pane B (repo)     liaison init, attach, validate, observe-session complete
Pane C (optional) liaison tui or command center JSON refresh
```

Liaison does **not** stream agent tool calls. After pane A finishes, run **`liaison observe-session complete`** (or `bin/liaison-session-done`) to write venture-grade artifacts into `.spark-flow/tasks/<task-id>/`.

## Workstation capacity

[`registry/workstation_profile.yaml`](../registry/workstation_profile.yaml) defines engine slots (`hermes`, `qca`, `ml_intern`, …) and `max_active_ventures`. The dashboard gate strip shows **Slots N/M** and queue depth.

## Venture-bound sessions

Register when spawning:

```bash
liaison terminal-session register \
  --agent-name hermes \
  --launch "cd ~/spark && hermes" \
  --project sigma \
  --task-id sigma-slice-1 \
  --pattern hermes-led-slice
```

Or:

```bash
liaison observe-session start --agent hermes --launch "..." --project sigma --task-id sigma-slice-1
```

## End of session (required)

On **failure** (non-zero exit), Liaison appends:

- `OBSERVATIONS.md`
- `events.jsonl` (`executor_session_end`)
- `EVALUATIONS.md` (fail)
- `LEARNINGS.md` (draft)

```bash
liaison observe-session complete \
  --agent hermes \
  --exit-code 1 \
  --project sigma \
  --task-id sigma-slice-1 \
  --log-file /tmp/hermes.log

# Or from repo with operator_session.json:
bin/liaison-session-done hermes 1 /tmp/hermes.log
```

On **success** (`exit-code 0`), observation + event only (no auto-fail eval).

Optional attach on complete (files report to outbox; approval stays manual):

```bash
liaison observe-session complete \
  --agent hermes --exit-code 0 --project sigma --task-id sigma-slice-1 \
  --attach-file ./report.md --attach-title "Hermes slice report"
```

Wrapped tmux spawn (dashboard `POST /api/terminal/spawn` with project + task): launch runs, then `observe-session complete` on exit. One-liner pattern:

```bash
bash -lc 'hermes ...; EXIT_CODE=$?; liaison observe-session complete --agent hermes --exit-code $EXIT_CODE --project sigma --task-id sigma-slice-1; exit $EXIT_CODE'
```

## Venture queue

Lightweight cross-project queue at `memory/venture_queue.json`:

```bash
liaison venture-queue add --project clinical_suite --task-id clinical-slice-1 --agent hermes
liaison venture-queue list
liaison venture-queue next              # hints only
liaison venture-queue next --spawn      # tmux/wezterm when TERMINAL_BRIDGE allows
LIAISON_AUTO_SPAWN=1 liaison venture-queue next
liaison venture-queue mark-running <item_id>
liaison venture-queue mark-done <item_id>
```

Web: `POST /api/venture-queue/next?spawn=1` when tmux available. Dashboard **Next + spawn** in Execution bridge when `terminal_bridge.spawn_allowed` is true.

## Log session watcher

Lightweight tail watcher (no inotify) — completes `observe-session` when a log stabilizes, a marker file appears, or a watched PID exits:

```bash
liaison observe-session watch \
  --log-file /tmp/hermes.log \
  --agent hermes \
  --project sigma \
  --task-id sigma-slice-1

# Or wrapper:
bin/liaison-watch-session --log-file /tmp/hermes.log --agent hermes --project sigma --task-id t1

# Optional: --marker-file /tmp/done.marker (contents may be exit code)
# Optional: --pid 12345 --stable-seconds 8
```

Runs `tail -F` in the background, polls log mtime/size stability (default 8s), then `observe-session complete`.

## Operator loop (off Cursor training wheels)

1. Focus project in dashboard (`?project=`).
2. `liaison init` / `start-pattern` in pane B.
3. Open executor in pane A (Hub → Open in terminal passes project + task).
4. When pane A ends: **`observe-session complete`** in pane B.
5. `liaison attach` if a report file exists → approve → validate → close-task.
6. Weekly: `liaison export-agent-recipe --from-project <key> --write`.

Cursor remains optional for editing `liaison_agentSystem` itself, not for portfolio operations.

## Dashboard / JSON

`liaison command-center --json` includes:

- `workstation_usage`
- `venture_queue`, `venture_queue_summary`
- `terminal_sessions` (venture fields; `pid` when tmux spawn captures pane PID)
- Kanban tasks: `last_executor_outcome`, `bound_agent`
- `summary.executor_session_stale` when venture-bound sessions lack `observe-session complete`
- **Phase controls:** `focus.project_phase`, `active_task_phase`, `workflow_phases`, `next_workflow_step`
- **Intake tiers:** `summary.ready_to_build_strict`, `ready_to_build_soft`, `executor_launch_ready`
- **Workflow hint:** `workflow_next_action` when reporter steps are done except close
- **Terminal bridge:** `terminal_bridge` (`mode`, `spawn_allowed`)

### Browser allowlist (Ops)

Safe POST via `/api/liaison/run`:

- `liaison validate --profile <known>` (focused project)
- `liaison approve-artifact <outbox-filename.md>` (open task outbox)
- `liaison close-task` (reporter steps ready except close)
- `liaison start-pattern <pattern_id>` (hub pattern scaffold)

**Phase controls (Track E1.2):** **Run next workflow step** runs the first gated allowlisted row from `suggested_workflow_commands`; each row also has **Run** (confirm + audit). Stdout appears in-panel; dashboard hard-refreshes on success.

**Reporter step advance (Track E1.3):** When `reporter_auto_advance: true` in `registry/project_plans.yaml`, Phase controls show **Advance reporter step** → `POST /api/liaison/reporter-step/advance`. Never uses `--force`; blocks on pending outbox / approve probes. Audit: `memory/browser_liaison_audit.jsonl`.

### Two phase concepts

| Concept | Source | Meaning |
|---------|--------|---------|
| **Project phase** | `.spark-flow/memory/project_phase.json` + registry | Maturity (prototype → alpha → mvp). Commands: `liaison assess-project`, `liaison project-phase show/advance`. |
| **Task phase** | Task `STATE.txt` `CURRENT_PHASE` | Slice lifecycle (plan → build → review → close). Commands: `liaison start build`, `liaison approve`, `liaison close-task`. |

The dashboard **Phase controls** panel (Overview / Workstream) shows both with copy-only commands. Operating-plan **workflow** YAML phases (`workflow_phases`, `next_workflow_step`) are hints only — no auto advance. When reporter steps are complete except close, JSON sets `workflow_next_action` with a `close-task` copy block.

## Shipped (P3a)

- **`workload_id` gate chip** — `summary.workload_id` from env or `PROJECT_PHASE.md`; web `GateStrip` + TUI `#gate-strip`.
- **TUI gate strip parity** — phase, validate, blockers, intake, build strict/soft, slots, queue, stale, flywheel, workload.
- **`suggested_workflow_commands`** — copy-only workflow hints from `next_workflow_step`; Phase controls panel.

## Deferred (P3b+)

Remaining ranked work lives in [finish-backlog/README.md](finish-backlog/README.md) (canonical Tracks 0–F):

- Full workflow YAML auto-execution ([Track E](finish-backlog/track-e-workflow-auto.md))
- Fly.io / Vercel production deploy for `dashboard/web` ([Track D](finish-backlog/track-d-production.md))
- TUI 3-column redesign ([Track C3.5](finish-backlog/track-c-command-center.md))
- Full inotify log watchers ([Track F](finish-backlog/track-f-non-goals.md) / E3)
- Direct Hermes skill file mutation (cancelled — use `export-learning-bridge`)

See [integrated-operator-model.md](integrated-operator-model.md) and [build-corpus-and-custom-agent.md](build-corpus-and-custom-agent.md).

## E2E operator smoke (A.6)

Dry-run checklist for sigma + clinical_suite paths (no live tmux):

```bash
bash tests/e2e_operator_smoke.sh
```

Checks: JSON smoke, focused project JSON, venture-queue list, `observe-session` CLI, `liaison-session-done`, snapshot script, wave-1 bootstrap. Training wheels: [operator-training-wheels.md](operator-training-wheels.md).
