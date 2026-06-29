# VERSION_FREEZE — Liaison v0.2.0

## Version Declaration

**Liaison v0.2.0** is the first stable release of the liaison control plane with:
- Durable task queue and evidence artifacts
- Human-in-the-loop approval gates
- Executor adapter contracts (shell, opencode, codex, claude_code)
- Worker run-once with validation gating
- Portfolio task generation and CLI
- Unified root CLI with subcommand groups

## Frozen Scope

The following are **frozen** for v0.2.0 and will not change without a version bump:

| Area | Status | Notes |
|------|--------|-------|
| Task queue states | Frozen | backlog → active → review_required → blocked/failed/done/cancelled |
| Required run artifacts | Frozen | 20 artifacts listed in `REQUIRED_RUN_ARTIFACTS` |
| Validation profiles | Frozen | `config/validation_profiles.yaml` structure |
| Executor adapter interface | Frozen | `run_executor()`, `ExecutorResult`, `ExecutorStatus` |
| Portfolio registry schema | Frozen | `registry/project_registry.active.yaml` |
| CLI subcommand groups | Frozen | portfolio, worker, evidence, gate, executor |
| Phase routing schema | Frozen | `registry/phase_routing.yaml` |

## Deferred to v0.3.0+

- Real NIM endpoint execution (Phase 8B)
- Remote result approval handoff (Phase 8C)
- ML-Intern sandbox integration (Phase 9)
- Dashboard auto-execution (Track E)
- Production deployment (Vercel/Fly.io)

## Compatibility

- Python ≥ 3.10
- Textual ≥ 0.47 (TUI)
- Next.js 14 (web dashboard)
- No breaking changes to registry YAML schemas within v0.2.x

## Version Location

- `config/executors.yaml`: `version: 0.2.0`
- `config/model_routes.yaml`: `version: 0.2.0`
- `config/budgets.yaml`: `version: 0.2.0`
- `registry/workflows.yaml`: `version: 1`
- `policies/validation_execution.yaml`: `version: "0.2.0"`

## Release Checklist

- [ ] All v0.2.0 tests pass (190 tests)
- [ ] 2 pre-existing failures documented and accepted
- [ ] Registry schemas validated
- [ ] CLI help outputs verified
- [ ] Dashboard loads without console errors