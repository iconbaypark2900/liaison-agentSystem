# Workflow YAML audit (B.4)

Inventory of `workflows/*.yaml`: linkage to `registry/project_plans.yaml`, phase count, and stub vs actionable heuristics.

Parent: [finish-backlog/track-b-portfolio.md](finish-backlog/track-b-portfolio.md)

**Heuristic**

| Label | Rule |
|-------|------|
| **Stub** | `status: stub`, or explicit scaffold-only note, or phases lack executable `liaison`/`spark-flow` commands |
| **Actionable** | Phases name agents/routes/skills and include operator commands operators can run today |

---

## Inventory

| File | Linked `project_plans` key | Phase count | Stub vs actionable | Notes |
|------|---------------------------|-------------|-------------------|--------|
| [workflows/sigma-integration.yaml](../workflows/sigma-integration.yaml) | `sigma` (`workflow_source` in plan) | 3 (`archive-inspect`, `module-validate`, `closeout`) | **Stub** | `status: stub`; declarative scaffold only — no auto-execution. Phases list `liaison init/validate/close-task` but marked reporter-first proof, not wired to spark-flow auto phases. |
| [workflows/data-flywheel.yaml](../workflows/data-flywheel.yaml) | — (hub workflow; plan uses `data-flywheel` via agent registry, not a DGX project key) | 8 named phases (`observe` … `learn`) | **Actionable** | Full artifact + command matrix; maps to `registry/workflows.yaml` `data-flywheel` and checks/data-flywheel.sh. Quality gates documented. |
| [workflows/python-cli.yaml](../workflows/python-cli.yaml) | `clinical_suite`, `adaptive_graph_rag`, `materialScience` (via `workflow: reporter-mode` / generic python profile — not this file directly) | 6 (`plan`, `build`, `test`, `patch`, `review`, `close`) | **Actionable** | Generic spark-flow phase routes (`reviewer`, `coder`, `deterministic`); listed in `registry/workflows.yaml` as `python-cli`. No project-specific IDs. |
| [workflows/quantum-ising.yaml](../workflows/quantum-ising.yaml) | — (quantum profile repos; no dedicated plan `workflow_source` pointer) | 6 (`quantum_plan` … `close`) | **Actionable** | Remote read-only `ising_analysis` phase; matches `registry/workflows.yaml` `quantum-ising`. Used for QCA / quantum validation lanes. |

---

## Cross-reference: `project_plans` workflow fields

| Plan key | `workflow` field | `workflow_source` |
|----------|------------------|-------------------|
| `sigma` | `sigma-integration` | `workflows/sigma-integration.yaml` |
| `clinical_suite` | `reporter-mode` | `registry/workflows.yaml` |
| `adaptive_graph_rag` | `reporter-mode` | `registry/workflows.yaml` |
| `research` | `ml-research` | `config/skill_resolution.yaml` (not under `workflows/`) |
| `materialScience` | `reporter-mode` | `registry/workflows.yaml` |

---

## Gaps

- Only **sigma-integration.yaml** is project-bound under `workflows/`; Tier A walkthrough repos mostly use **reporter-mode** from registry, not standalone YAML files.
- **research** workflow lives in skill resolution config, not audited here — extend audit if ml-research YAML is added later.
- Track E ([track-e-workflow-auto.md](finish-backlog/track-e-workflow-auto.md)) owns auto-execution; this table is inventory only.

---

## Regenerate

Re-read YAML after edits:

```bash
ls -1 workflows/*.yaml
# Update phase counts and stub/actionable column manually or extend a small script in tests/
```
