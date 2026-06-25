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
|------|---------------------------|-------------|-------------------|-------|
| [workflows/sigma-integration.yaml](../workflows/sigma-integration.yaml) | `sigma` (`workflow_source` in plan) | 3 (`archive-inspect`, `module-validate`, `closeout`) | **Stub** | `status: stub`; declarative scaffold only — no auto-execution. Phases list `liaison init/validate/close-task` but marked reporter-first proof, not wired to spark-flow auto phases. |
| [workflows/data-flywheel.yaml](../workflows/data-flywheel.yaml) | — (hub workflow; plan uses `data-flywheel` via agent registry, not a DGX project key) | 8 named phases (`observe` … `learn`) | **Actionable** | Full artifact + command matrix; maps to `registry/workflows.yaml` `data-flywheel` and checks/data-flywheel.sh. Quality gates documented. |
| [workflows/python-cli.yaml](../workflows/python-cli.yaml) | `clinical_suite`, `adaptive_graph_rag`, `materialScience` (via `workflow: reporter-mode` / generic python profile — not this file directly) | 6 (`plan`, `build`, `test`, `patch`, `review`, `close`) | **Actionable** | Generic spark-flow phase routes (`reviewer`, `coder`, `deterministic`); listed in `registry/workflows.yaml` as `python-cli`. No project-specific IDs. |
| [workflows/quantum-ising.yaml](../workflows/quantum-ising.yaml) | — (quantum profile repos; no dedicated plan `workflow_source` pointer) | 6 (`quantum_plan` … `close`) | **Actionable** | Remote read-only `ising_analysis` phase; matches `registry/workflows.yaml` `quantum-ising`. Used for QCA / quantum validation lanes. |
| [workflows/rag-app.yaml](../workflows/rag-app.yaml) | `adaptive_graph_rag` (candidate) | 6 (`rag_plan`, `corpus_prep`, `retrieval_build`, `rag_validate`, `rag_review`, `close`) | **Actionable** | RAG lifecycle: plan, corpus prep, retrieval build, deterministic validation, review, close. `validation_profile: rag` → `checks/rag.sh`. |
| [workflows/quantum-benchmarks.yaml](../workflows/quantum-benchmarks.yaml) | QCA / quantum benchmark plans (candidate) | 6 (`benchmark_plan`, `backend_setup`, `benchmark_run`, `quantum_validate`, `analysis_review`, `close`) | **Actionable** | Quantum benchmark lifecycle with remote read-only run. `validation_profile: quantum` → `checks/quantum.sh`. |
| [workflows/ml-research.yaml](../workflows/ml-research.yaml) | `research` (workflow pointer in `config/skill_resolution.yaml`) | 6 (`experiment_plan`, `data_prep`, `experiment_run`, `ml_research_validate`, `analysis_review`, `close`) | **Actionable** | ML research lifecycle; `validation_profile: ml-research` → `checks/ml-research.sh`. |
| [workflows/frontend-app.yaml](../workflows/frontend-app.yaml) | frontend projects (candidate) | 6 (`frontend_plan`, `scaffold`, `implement`, `frontend_validate`, `review`, `close`) | **Actionable** | Frontend lifecycle; `validation_profile: frontend` → `checks/frontend.sh`. |
| [workflows/backend-app.yaml](../workflows/backend-app.yaml) | backend projects (candidate) | 6 (`backend_plan`, `scaffold`, `implement`, `backend_validate`, `review`, `close`) | **Actionable** | Backend lifecycle; `validation_profile: backend` → `checks/backend.sh`. |
| [workflows/scientific-paper.yaml](../workflows/scientific-paper.yaml) | paper authoring (candidate) | 8 (`outline`, `experiment_evidence`, `draft`, `internal_review`, `revise`, `coauthor_approval`, `submit`, `close`) | **Actionable** | Scientific paper lifecycle with explicit co-author approval and submission gates. |
| [workflows/portfolio-optimizer.yaml](../workflows/portfolio-optimizer.yaml) | portfolio optimization (candidate) | 8 (`strategy_plan`, `data_prep`, `backtest`, `risk_review`, `strategy_validate`, `paper_trade`, `live_allocation`, `close`) | **Actionable** | Portfolio strategy lifecycle; paper trading required before live capital allocation, both approval-gated. |
| [workflows/qids.yaml](../workflows/qids.yaml) | QIDS modules (candidate) | 6 (`qids_plan`, `module_design`, `calibration`, `qids_validate`, `integration_review`, `close`) | **Actionable** | Quantum-Inspired Decision System module lifecycle; remote read-only calibration gated by approval. |

---

## Cross-reference: `project_plans` workflow fields

| Plan key | `workflow` field | `workflow_source` |
|----------|------------------|-------------------|
| `sigma` | `sigma-integration` | `workflows/sigma-integration.yaml` |
| `clinical_suite` | `reporter-mode` | `registry/workflows.yaml` |
| `adaptive_graph_rag` | `reporter-mode` / candidate `rag-app` | `registry/workflows.yaml` / `workflows/rag-app.yaml` |
| `research` | `ml-research` | `workflows/ml-research.yaml` (and `config/skill_resolution.yaml`) |
| `materialScience` | `reporter-mode` | `registry/workflows.yaml` |

---

## Gaps

- **sigma-integration.yaml** is the only project-bound workflow under `workflows/` that is still marked `status: stub`; the new pack workflows (rag-app, quantum-benchmarks, ml-research, frontend-app, backend-app, scientific-paper, portfolio-optimizer, qids) are all `actionable` but project-plan linking is optional and not yet wired.
- Track E ([track-e-workflow-auto.md](finish-backlog/track-e-workflow-auto.md)) owns auto-execution; this table is inventory only.

---

## Regenerate

Re-read YAML after edits:

```bash
ls -1 workflows/*.yaml
# Update phase counts and stub/actionable column manually or extend a small script in tests/
```
