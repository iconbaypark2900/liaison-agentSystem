# Roadmap

## Completed

* Phase 1: Registries and policies
* Phase 2: Read-only inspection commands
* Phase 3: Context bundles
* Phase 4: Remote request skeleton
* Phase 5: Research-worker skeleton
* Phase 6: Safe validation profiles
* Phase 7: Conductor hardening
* Phase 7B: Context hygiene hardening
* Phase 8A: NIM remote dry-run payload builder
* Phase 8B: Real NIM endpoint execution (gated by NVIDIA_API_KEY + approval + budget)
* Phase 8C: Remote result approval and handoff
* Phase 9: Real ML-Intern sandbox integration (gated by ml-intern tool + sandbox enforcement)
* Phase 10: Workflow packs
* Phase 11: Dashboard panels (tasks, approvals, validation, routing, context bundles, logs, budgets)

## Next

All planned phases are complete. The system is ready for activation when
external dependencies are available:

* **NVIDIA_API_KEY** — set this env var and create approved request files to
  enable real NIM endpoint calls via `liaison remote run <capability>`
* **ml-intern** — install the CLI tool and set `ml_intern.enabled: true` in
  `config/executors.yaml` to enable sandbox research runs via
  `liaison research run ml_intern`
