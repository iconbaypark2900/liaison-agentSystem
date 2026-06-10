# Track E — Workflow automation (P3b XL, phased)

**Purpose:** Move from copy-only workflow hints to guarded auto-execution. **Do not start** until [B.4 workflow audit](track-b-portfolio.md) + [C3.3 allowlist hardening](track-c-command-center.md) exist.

[Index ←](README.md)

---

## Phase E0 — Reporter step machine (foundation)

| ID | Title | Size | Done when |
|----|--------|------|-----------|
| **E0.1** | Step transition API (CLI) | M | **Done** — `liaison reporter-step show\|set\|advance` writes `reporter_step_state.json`; idempotent |
| **E0.2** | JSON exposes `reporter_step_state` | S | **Done** — Command center shows current step + `allowed_next`; ReporterChecklist highlights current |
| **E0.3** | Policy gate map | M | **Done** — `policies/reporter-step-gates.md` + `registry/reporter_step_gates.yaml` |

---

## Phase E1 — Copy-only++ → guarded auto (M/L)

| ID | Title | Size | Done when |
|----|--------|------|-----------|
| **E1.1** | Wire `suggested_workflow_commands` to gates | M | **Done** — PhaseControlsPanel disables copy until soft-ready + validate before close-task |
| **E1.2** | Allowlisted auto via browser | M | **Done** — Phase controls **Run next workflow step** / per-row **Run** with confirm + `browser_liaison_audit.jsonl` |
| **E1.3** | Phase auto-advance (opt-in) | L | **Done** — `reporter_auto_advance` in `project_plans.yaml`; explicit **Advance reporter step** button (no `--force`) |

---

## Phase E2 — Full YAML auto-execution (XL)

| ID | Title | Size | Done when |
|----|--------|------|-----------|
| **E2.1** | Workflow runner service | XL | Reads `workflows/*.yaml`; allowlisted liaison subcommands only |
| **E2.2** | Venture queue integration | M | Queue `next` attaches workflow run id; complete advances pointer |

---

**Deferred unless proven needed:** **E3** full inotify watchers (keep `observe-session watch`). See [Track F](track-f-non-goals.md).
