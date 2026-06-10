# Operator quick reference

One-page companion to [integrated-operator-model.md](integrated-operator-model.md). For full narrative and diagrams, read that doc. For CLI details, see [command_reference.md](command_reference.md).

---

## Model (one line)

Hermes and specialists run in the terminal; Liaison governs on disk; web and TUI mirror `liaison command-center --json`.

---

## Surfaces

| Surface | Start |
|---------|--------|
| Web | `cd dashboard/web && npm run dev` → http://localhost:3000 |
| TUI | `liaison command-center` or `liaison tui` |
| JSON | `liaison command-center --json --refresh` |

---

## Home tabs (`/`)

| Tab | Use |
|-----|-----|
| **Overview** | Gate strip, phase controls, intake, overview actions, reporter checklist |
| **Workstream** | Focused project kanban, project detail, hub workflows, reporter steps |
| **Ops** | Signoff playbook, pending handoffs, validate/approve/close allowlist |

Other routes: `/projects`, `/hub`, `/rolodex`, `/ops`, `/settings`.

---

## Gate strip + workload

Web **GateStrip** and TUI **`#gate-strip`** mirror `summary` from JSON:

- Phase / validate / blockers · intake ready · build strict/soft · executor launch ready
- Workstation **Slots N/M** · venture queue depth · stale executor sessions
- **Flywheel tasks: N** · optional **Workload** chip from `summary.workload_id` (env `LIAISON_WORKLOAD_ID` or repo `PROJECT_PHASE.md`)
- **Debrief stale** when `summary.debrief_stale` (default threshold 7 days — `command_center.debrief_stale_days` in `validation_profiles.yaml`)

**Sync liaison** (`?refresh=1`) after disk changes.

---

## Phase controls + workflow copy

**Phase controls** (Overview / Workstream): project phase vs task phase; copy-only liaison commands.

JSON **`suggested_workflow_commands`** — next workflow YAML step as copy buttons (not auto-exec). See **`workflow_phases`**, **`next_workflow_step`**, **`workflow_next_action`**.

---

## Execution bridge

Full doc: [execution-bridge.md](execution-bridge.md).

| Action | Command |
|--------|---------|
| Start venture session | `liaison observe-session start …` or `terminal-session register` |
| End session (required) | `liaison observe-session complete …` or `bin/liaison-session-done <agent> <exit> [log]` |
| Log watcher | `liaison observe-session watch …` or `bin/liaison-watch-session` |
| Queue | `liaison venture-queue add|list|next|mark-running|mark-done` |
| Auto spawn | `venture-queue next --spawn` or `LIAISON_AUTO_SPAWN=1` |

Training wheels (Cursor hooks, snapshot cron): [operator-training-wheels.md](operator-training-wheels.md).

---

## tmux / terminal layout

```text
Pane A   Hermes / QCA / ML Intern / Unsloth   (Copy launch or Open in terminal from /hub)
Pane B   cd <registered-repo>                  (liaison init, attach, approve, validate, close)
Pane C   liaison command-center                (optional keyboard cockpit)
```

Set `TERMINAL_BRIDGE=tmux` or `wezterm` in `dashboard/web/.env.local` so **Open in terminal** spawns a pane (see [../dashboard/README.md](../dashboard/README.md)).

---

## Six-step choreography

1. **Orient** — select project (`?project=`), task (`?task=`), pattern (`?pattern=`), gate strip, reporter checklist, hub groups.
2. **Arm** — open panes A/B (and C if using TUI).
3. **Execute** — run agent in A; watch output.
4. **Govern** — `liaison attach …` in B; approve, validate, gate.
5. **Close** — `close-task`, debrief, `promote-learning` as needed.
6. **Reflect** — **Sync liaison** on web or `liaison look --refresh`; JSON updates without blanking UI (`keepPreviousData`).

---

## Hub groups

| Group | Agents | Terminal |
|-------|--------|----------|
| Executors | hermes, qca, ml_intern, unsloth_studio | Run launch line in pane A |
| Liaison lanes | liaison, data_flywheel (Data flywheel workflow) | CLI only; attach reports |
| Exceptional phase | codex, opencode, claude | Prefer Hermes + attach; phase lane only when Flow owns branch |

---

## Trigger matrix (condensed)

| Goal | Terminal | Dashboard |
|------|----------|-------------|
| Engineering | `hermes` (from launch) | Copy launch / Open in terminal |
| Multi-agent slice | `liaison start-pattern <id>` | Pattern picker → Scaffold |
| Record output | `liaison attach <agent> --text "…"` | Copy attach; Ops after refresh |
| Flywheel | `liaison init` + data-flywheel workflow | Liaison lanes + handoff chains |
| Portfolio scan | `liaison look --refresh` | `/` gates + matrix |
| Keyboard | `liaison command-center` | Same data as web |

Never run executors from the Next.js API.

---

## Copy commands (templates)

From project repo (pane B):

```bash
liaison init <task-id> "One focused goal"
liaison snapshot --show
liaison attach hermes --title "Report" --text "<paste agent output>"
liaison approve-artifact <report.md>
liaison decision "Approved approach"
liaison validate
liaison gate --show
liaison close-task --summary "Done"
```

Multi-agent scaffold:

```bash
liaison start-pattern <pattern-id> --task-id <task-id> --description "Slice label"
```

Refresh aggregate state:

```bash
liaison look --refresh
liaison command-center --json --refresh
```

Web: **Refresh data** on Control column or Settings (hard `?refresh=1`).

---

## TUI keybindings (command center)

| Key | Context | Action |
|-----|---------|--------|
| `1`–`5` | Any tab (not rolodex list) | Rolodex category shortcuts (Skills … Tools) |
| `1`–`9` | Rolodex tab (items/detail focused) | Copy numbered **Actions** entry |
| `!` | Focused panel | Copy selected liaison command |
| `x` / Enter | Focused panel | Run read-only liaison command |
| `r` | Any | Refresh JSON state |
| Tab | — | Overview · Rolodex · Hub · Workstream · Ops |

Overview layout: **≥120** terminal columns → three columns (actions · brief · signoff); narrower terminals stack gracefully.

---

## Refresh rule

Disk changes (`attach`, `approve`, `close-task`, `start-pattern`) → then `look --refresh` or dashboard hard refresh → web/TUI show new handoffs and gates. Poll alone may lag up to `refresh_sec` (default 30s).

---

## Backlog & upgrades

- Shipped A–H + P1–P3a: [operator-upgrades-roadmap.md](operator-upgrades-roadmap.md)
- Finish-line program (Tracks 0–F): [finish-backlog/README.md](finish-backlog/README.md)
