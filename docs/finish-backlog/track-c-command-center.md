# Track C — Command center depth (R2–R5)

**Purpose:** Finish dashboard/TUI UX without auto-exec policy risk. Best if you want “finish UX” before hosting or workflow automation.

[Index ←](README.md) · **Roadmap checklist:** [command-center-upgrade-roadmap.md](../command-center-upgrade-roadmap.md)

## Sprint C1 — R2 Hub connection (M)

| ID | Title | Size | Status | Files (primary) | Done when |
|----|--------|------|--------|-----------------|-----------|
| **C1.1** | Deep links `?agent=` / `?pattern=` | S | **Done** | `url-query-helpers.ts`, `AgentHubList`, `PatternPicker` | `/hub?agent=hermes&pattern=…` selects agent + pattern |
| **C1.2** | Sticky Intake → Plan → Hub bar | M | **Done** | `PlaybookProgressBar.tsx`, `CommandCenterTabs.tsx` | Progress strip on home; Hub link preserves session |
| **C1.3** | One-click handoff play blocks | M | **Done** | `operator-templates.ts`, `HandoffChainCards.tsx` | Per-edge **Copy** (`ml_intern → qca`) on each chain |
| **C1.4** | Pattern → agent graph | L | **Done** | `PatternAgentGraph.tsx`, hub + `HubColumn` | Clickable agent nodes → `/hub?agent=…&pattern=…` |

**Deps:** C1.1 before C1.4.

---

## Sprint C2 — R3 Workstream depth (M)

| ID | Title | Size | Done when |
|----|--------|------|-----------|
| **C2.1** | Matrix row intake/plan/corpus preview | M | **Done** | Unfocused row expand shows lightweight intake/plan/corpus |
| **C2.2** | `BuildCorpusPanel` | M | **Done** | Web panel: traces summary, export/recipe copy actions |
| **C2.3** | Kanban task reporter expand | S | **Done** | Task row expands `reporter_steps` + link to `?task=` |

---

## Sprint C3 — R4 Ops + R5 TUI (M)

| ID | Title | Size | Done when |
|----|--------|------|-----------|
| **C3.1** | Debrief staleness on gate strip / Ops | S | **Done** | Red chip when debrief > N days |
| **C3.2** | Flywheel drill-down on Ops | M | **Done** | Ops links flywheel tasks → workflow YAML step list |
| **C3.3** | Browser allowlist hardening | M | **Done** | Confirm dialogs + scoped project/task; audit log |
| **C3.4** | TUI rolodex action picker 1–9 | M | **Done** | `app.py`: pick which `actions[]` entry `!` copies |
| **C3.5** | TUI 3-column overview (L8) | L | **Done** | Large terminal: overview columns; gate strip retained |

---

**Track C milestone:** R2–R5 checklist in [command-center-upgrade-roadmap.md](../command-center-upgrade-roadmap.md) marked **Done** except deferred items.
