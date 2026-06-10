# Command center upgrade roadmap (R1–R6)

Phased upgrade for **Textual TUI** (`dashboard/command_center/app.py`) and **Next.js dashboard** (`dashboard/web/`). JSON SSOT: `collect_command_center_state` in `dashboard/command_center/data.py`.

**Legend:** Done = shipped in tree · Partial = foundation only · Planned = not started

---

## User asks → phases

| # | User requirement | Phase | Status |
|---|------------------|-------|--------|
| 1 | Rolodex right panel: spec-driven detail, actions, steps, paths | **R1** | **Done** |
| 2 | Overview: actionable intake/plan/sync/hub rows + situation briefs | **R1** | **Done** |
| 3 | Hub: handoff chains, pattern graph, copy play | **R2** | Partial |
| 4 | Projects in rolodex + workstream reports | **R1** | **Done** |
| 5 | Ops = final signoff (playbook + how-to per step) | **R1** | **Done** |
| 6 | Dashboard linking Intake → Plan → Playbook → Hub | **R1–R2** | Partial |
| 7 | TUI same IA as web | **R1** | **Done** |

---

## R1 — Spec-driven rolodex + ops signoff (this session)

**Goal:** Smallest slice visible in browser and TUI after `npm run dev` and `liaison tui`.

| Area | Files | Delivered |
|------|-------|-----------|
| Rolodex actions | `rolodex.py` | `actions: [{label, liaison_cmd}]` on all categories; `format_detail` shows steps, agents, checklist |
| All registered projects | `project_plans.py` | `build_projects_registry`, `build_registry_rolodex_entries`; merged into `rolodex.projects` |
| Ops signoff JSON | `data.py` | `ops_signoff`, `overview_actions`, `projects_registry` on state |
| TUI Overview | `app.py` | `OverviewActionsList`; ops summary + checklist preview |
| TUI Workstream | `app.py` | `#project-report` intake/plan/corpus strip when focused |
| TUI Ops | `app.py` | `_show_signoff_detail` default; handoffs first |
| TUI Hub | `app.py` | Handoff chain hints under agent detail |
| Web Overview | `OverviewActions.tsx`, `/` | Sync, intake, plan, hub links |
| Web Ops | `OpsSignoffPanel.tsx`, `/ops` | Checklist, pending handoffs, copy hints |
| Web Rolodex | `RolodexPanel.tsx`, `/rolodex`, `/hub` | Category tabs + detail drawer |
| Web Projects | `WorkstreamProjectReport.tsx`, `/projects` | Expandable registry rows |
| Types | `command-center-types.ts` | `RolodexEntry`, `OpsSignoff`, `ProjectRegistryEntry` |
| Tests | `test_rolodex.py`, `ops-signoff.test.ts` | Registry count ≥ repos; ops_signoff shape |

### R1.1 — Rolodex operator-readable detail

| Rolodex detail UX | `rolodex.py`, `hub_skills.py`, `rolodex_resume.py`, `registry/rolodex_profiles.yaml`, `RolodexPanel.tsx` | Structured **resume** (Profile, Capabilities, Best for, When to use, Outputs, Limits) from SKILL.md + curated profiles; What / Next steps unchanged |

### Verify R1

**TUI**

```bash
cd /path/to/liaison_agentSystem
liaison tui
```

- **Overview:** Quick actions list on row 3 right; `!` / `x` on selected action.
- **Rolodex → Projects:** Every `registry/repos.yaml` entry plus patterns; detail shows Actions + workflow steps.
- **Workstream:** Select project → `#project-report` strip under reporter checklist.
- **Ops:** Default detail = signoff checklist + copy hints; handoffs list on left.

**Web**

```bash
cd dashboard/web && npm run dev
```

- **`/`** — Overview actions panel above intake.
- **`/rolodex`** — Full rolodex; **`/hub`** — compact rolodex at bottom.
- **`/ops`** — OpsSignoffPanel above handoffs table.
- **`/projects`** — Registered projects expandable cards.

**JSON**

```bash
liaison command-center --json | jq '.ops_signoff.checklist | length, .projects_registry | length, .rolodex.projects | length'
```

---

## R2 — Hub connection UX

| Item | Files | Notes |
|------|-------|-------|
| Pattern → agent graph | `HandoffChainCards.tsx`, new graph component | Visual edges from `project_agent_patterns` |
| Quick copy play between agents | `operator-templates.ts`, `HubColumn` | One-click handoff play blocks |
| Rolodex ↔ hub deep links | `url-query-helpers.ts`, hub page | `?agent=` / `?pattern=` opens detail |
| Intake → Plan → Hub strip | `/` layout | Sticky playbook progress bar |

---

## R3 — Workstream depth

| Item | Files | Notes | Status |
|------|-------|-------|--------|
| Matrix row → full intake/plan/corpus | `ProjectMatrixTable.tsx`, `project_portfolio.py` | `projects_portfolio_detail[]` — expand row without focus | **Done** |
| Build corpus review UI | `BuildCorpusPanel.tsx` | Traces summary + `record-build` / `export-agent-recipe` copy | **Done** |
| Kanban task → reporter bundle | `KanbanBoard.tsx` | Expand task with `reporter_steps`; `?task=` via context | **Done** |

---

## R4 — Ops automation

| Item | Files | Notes | Status |
|------|-------|-------|--------|
| Browser allowlist execute for approve/validate | `liaison-exec.ts`, `liaison-run-client.ts`, `route.ts` | Scoped writes with confirmation + `memory/browser_liaison_audit.jsonl` | **Done** |
| Debrief staleness alerts | `OpsSignoffPanel`, `GateStrip`, `data.py` | Red when > N days (`command_center.debrief_stale_days`) | **Done** |
| Flywheel task drill-down | `OpsWorkspace.tsx`, `data.py` | Workflow YAML steps + init copy blocks when flywheel open | **Done** |

---

## R5 — TUI parity polish

| Item | Files | Notes | Status |
|------|-------|-------|--------|
| Gate strip inside TUI | `app.py` | Match web GateStrip chips | **Done** |
| Rolodex action picker (1–9) | `app.py`, `rolodex.py` | Digit copies numbered `actions[]`; `!` copies selected | **Done** |
| Three-column overview on large terminals | CSS in `app.py` | ≥120 cols: actions · brief · signoff; 2/1-col fallback | **Done** |

---

## R6 — Production & docs

| Item | Files | Notes |
|------|-------|-------|
| Deploy dashboard | Vercel / Fly | Out of scope for local Spark |
| Operator quick-ref update | `operator-quick-reference.md` | R1 keybindings |
| E2E smoke | `tests/test_command_center_json.sh` | ops_signoff keys |

---

## Implementation pointers

| JSON key | Builder |
|----------|---------|
| `rolodex` | `rolodex.build_rolodex` |
| `projects_registry` | `project_plans.build_projects_registry` |
| `ops_signoff` | `data.build_ops_signoff` |
| `overview_actions` | `data.build_overview_actions` |
| `project_intake` / `project_plan` / `build_corpus_summary` | Focused project only |
| `projects_portfolio_detail` | `project_portfolio.build_projects_portfolio_detail` — all registered repos |

Parent: [operator-upgrades-roadmap.md](operator-upgrades-roadmap.md) § P1.
