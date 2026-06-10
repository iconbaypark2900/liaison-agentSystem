# Operator upgrades roadmap (A–H)

Prioritized improvements for the integrated operator model ([integrated-operator-model.md](integrated-operator-model.md)). Status reflects the `liaison_agentSystem` tree after the A–H implementation pass.

**Legend**

| Status | Meaning |
|--------|---------|
| **Done** | Shipped and usable in web, TUI, or CLI |
| **Partial** | Foundation exists; spec not fully met |
| **Planned** | Not implemented |

---

## Shipped (execution bridge — track J)

- **`registry/workstation_profile.yaml`** — engine slots and max active ventures.
- **`liaison observe-session`** / **`terminal-session complete`** — venture-bound sessions; failure → observation + eval + learning on disk.
- **`liaison venture-queue`** — lightweight queue (`memory/venture_queue.json`) with capacity-aware `next`.
- **JSON:** `workstation_usage`, `venture_queue`, kanban `last_executor_outcome` / `bound_agent`.
- **Web:** `ExecutionBridgePanel`, gate strip slots, spawn API passes project/task/pattern.
- **Doc:** [execution-bridge.md](execution-bridge.md), `bin/liaison-session-done`.

## Shipped (command center layout + portfolio)

- **Home (`/`)** — Overview | Workstream | Ops tabs instead of one endless scroll.
- **Projects** — Matrix/kanban left; **project detail** (intent, agents, skills, production path, research commands) + **ranked hub workflows** right.
- **Hub** — Agent deck + scoped workflows + pattern picker + handoff chains.
- **Ops** — Shared `OpsWorkspace` (signoff playbook, reporter checklist, handoff/debrief previews).
- **Rolodex** — Category intros; richer commands/tools copy; registered repos use portfolio resume.
- **TUI** — Focused workstream shows full project detail text.
- **JSON fields** — `project_detail`, `project_portfolio`, `hub_workflows`, `overview_brief`, `workstream_brief`, `rolodex_category_intros`.

---

## Checklist

| ID | Title | Status | Owner surface | Notes |
|----|-------|--------|---------------|-------|
| **A** | Operator session object | **Done** | web / CLI | `?project=`, `?task=`, `?pattern=` in URL and `CommandCenterContext`. JSON returns `active_task_id`, `pattern_id`, `operator_session`. Optional `--persist-session` writes `.spark-flow/memory/operator_session.json` on focused repo. |
| **B** | Three-pane playbook on `/` | **Done** | web | `ReporterChecklist` with disk-backed `reporter_steps` (✓/○/!) from `probe_reporter_steps` in `data.py`. Clickable task rows bind `selectedTaskId`. |
| **C** | Event-ish refresh | **Done** | web | **Sync liaison** in `GateStrip` and `ControlColumn` calls `refresh(true)` (`?refresh=1`). `keepPreviousData` + debounced project/task/pattern fetch. Poll from `refresh_sec`. |
| **D** | Terminal session registry | **Done** | web / python | `memory/terminal_sessions.json`, `liaison terminal-session list|register|prune`, register on `POST /api/terminal/spawn`, gate-strip pills when `alive`. |
| **E** | Unified copy “play” block | **Done** | web | `buildReporterBundle` requires bound `taskId` + `liaison snapshot --show`. `buildPatternPlayBlock` inlines pattern YAML steps. **Copy full play** on `PatternPicker`. |
| **F** | TUI hub parity | **Done** | tui / web | `hub_agent_groups` in JSON; Hub tab section headers; Workstream `reporter-checklist` Static from `reporter_steps`. Hub + rolodex agent detail use structured `resume` (Profile, Capabilities, Best for, When to use) from `rolodex_profiles.yaml` + `hub_skills.yaml`. |
| **G** | Flywheel visibility | **Done** | web / TUI | Display name **Data flywheel (workflow)**; gate chips `Flywheel tasks: N` and optional `Workload` from `summary.flywheel_open` / `summary.workload_id`. |
| **H** | Phase executor warning | **Done** | web | Warning panel when exceptional-phase agent selected, using registry `launch_note`. |
| **I1** | Project intake pipeline | **Done** | web / CLI | `liaison project-intake`; `project_intake` in JSON; Intake panel; gate strip; soft-gate executors when `!ready_to_build`. |

---

## P1 — Command center UX (R1 slice)

Cross-surface upgrade for rolodex detail, overview actions, ops signoff, and registered-project visibility. **Status: Done (R1).**

| Surface | Shipped |
|---------|---------|
| JSON | `ops_signoff`, `overview_actions`, `projects_registry`; rolodex `actions[]`; all repos in `rolodex.projects` |
| TUI | Overview quick actions; workstream project report; ops signoff default; hub chain hints |
| Web | `OverviewActions`, `OpsSignoffPanel`, `RolodexPanel`, `WorkstreamProjectReport`; `/rolodex` route |

Full phase plan: [command-center-upgrade-roadmap.md](command-center-upgrade-roadmap.md).

---

## Implementation pointers (existing code)

| Area | Path |
|------|------|
| Hub groups (web) | `dashboard/web/src/lib/hub-agent-groups.ts`, `AgentHubList.tsx` |
| Hub groups (python) | `dashboard/command_center/hub_groups.py` |
| Reporter checklist | `ReporterChecklist.tsx`, `probe_reporter_steps` in `data.py` |
| Operator session | `dashboard/command_center/operator_session.py`, URL helpers `url-query-helpers.ts` |
| Pattern / play blocks | `operator-templates.ts`, `PatternPicker.tsx` |
| Terminal sessions | `terminal_sessions.py`, `api/terminal/spawn/route.ts` |
| Project intake | `project_intake.py`, `IntakePanel.tsx`, `liaison project-intake` |
| JSON SSOT | `collect_command_center_state` in `data.py` |
| Gate strip / workload | `resolve_workload_id`, `format_gate_strip_tui` in `data.py`; `GateStrip.tsx`; TUI `GateStripBar` in `app.py` |
| Workflow copy commands | `suggested_workflow_commands` in JSON; `PhaseControlsPanel.tsx` |
| TUI | `dashboard/command_center/app.py` |

---

## Build corpus (custom agent recipes)

| Piece | Path / command |
|-------|----------------|
| Doc | [build-corpus-and-custom-agent.md](build-corpus-and-custom-agent.md) |
| Record | `liaison record-build --agent hermes --action "…" --outcome "…"` |
| Export | `liaison export-agent-recipe --from-project <key> --write` |
| JSON | `build_corpus_summary` when command-center project focused |

---

## Out of scope (separate tracks)

- **L8 Textual 3-column redesign** (full three-column layout; compact gate strip shipped in P3)
- **Fly.io / production deploy** for `dashboard/web` — see [dashboard-web-deploy.md](dashboard-web-deploy.md)

Parent spec: [integrated-operator-model.md](integrated-operator-model.md#implemented-operator-upgrades-a-h).

---

## P1 — Operator readiness audit (shipped)

| Item | Shipped |
|------|---------|
| Phase controls panel | `PhaseControlsPanel` on Overview + Workstream; JSON `focus.project_phase`, `active_task_phase` |
| Tiered intake | `ready_to_build_strict` / `ready_to_build_soft`; gate strip; `executor_launch_ready` soft-gate |
| Workflow hints | `workflow_phases`, `next_workflow_step` from plan workflow YAML (copy only) |
| tmux PID on spawn | `POST /api/terminal/spawn` registers `--pid` via `tmux new-window -P -F '#{pane_pid}'` |
| Global ops handoffs | Unfocused ops shows cross-project pending handoffs with `?project=` links |
| Hub workflow scaffold | `HubWorkflowPanel` allowlisted POST like `PatternPicker` |
| Venture queue next | `hints.copy_block` with wrapped spawn + complete commands |

P3 slice 1 (gate strip + workload): shipped — see **P3 — Prioritized** below.

---

## P2 — Operator readiness (shipped)

| Item | Shipped |
|------|---------|
| Auto tmux spawn from queue | `venture-queue next --spawn`, `LIAISON_AUTO_SPAWN=1`, `POST /api/venture-queue/next?spawn=1`, **Next + spawn** in Execution bridge |
| Log tail watcher | `liaison observe-session watch`, `bin/liaison-watch-session` |
| Hermes learning bridge | `liaison export-learning-bridge --from-project <key>` → repo `.spark-flow/memory/hermes_hints.md` |
| Portfolio search/filter | `ProjectMatrixTable` filter + sort (score / name) on Projects + Workstream |
| pytest / CI hygiene | `pytest` in `requirements.txt`, `tests/run_smoke.sh`, `tests/README.md` |
| Workflow close hint | JSON `workflow_next_action`; browser allowlist for `close-task` when reporter steps ready |
| Browser validate / approve | Allowlist + Ops **Run validate** / **Approve** via `POST /api/liaison/run` |

## P3 — Prioritized

Ranked for the HITL multi-project operator vision (keyboard + web parity, flywheel visibility, copy-only workflow guidance before automation).

| Rank | Item | Rationale |
|------|------|-----------|
| 1 | **`workload_id` gate chip** | **Done (P3a).** Small L5 flywheel signal; env `LIAISON_WORKLOAD_ID` or `PROJECT_PHASE.md` → `summary.workload_id`; web `GateStrip` + TUI `#gate-strip`. |
| 2 | **TUI gate strip parity** | **Done (P3a).** Keyboard operators see same gates as web (phase, validate, blockers, intake, build strict/soft, slots, queue, stale, flywheel, workload). |
| 3 | **Workflow YAML step runner (copy-only++)** | **Done (P3a slice).** JSON `suggested_workflow_commands` from `next_workflow_step`; Phase controls copy buttons — not full auto-exec. |
| 4 | **Fly.io / production deploy** | Ops/doc track; no `vercel.json` in tree — stub [dashboard-web-deploy.md](dashboard-web-deploy.md). |
| 5 | **Full inotify log watchers** | Defer; `liaison observe-session watch` poll/tail is enough for now. |
| 6 | **Direct Hermes skill sync** | **Cancelled** — use `liaison export-learning-bridge` → `hermes_hints.md`. |

### P3b — Schedule next

**Canonical planning source:** [finish-backlog/README.md](finish-backlog/README.md) (Tracks 0–F — program plan, definition of done, priority table). P3b items are summarized in per-track files with acceptance criteria.

| Item | Notes |
|------|-------|
| Full workflow YAML auto-execution | Track E — requires policy gates + reporter step machine |
| Fly.io / Vercel production deploy | Track D — [dashboard-web-deploy.md](dashboard-web-deploy.md) |
| TUI 3-column redesign | Track C3.5 — layout pass after gate strip proves useful |
| Full inotify log watchers | Track F — only if poll/tail misses events in production |

### P3 — Remaining (unranked backlog)

All ranked items above are either done (1–3), stubbed (4), deferred (5), or cancelled (6). See **P3b** for the next engineering slices.
