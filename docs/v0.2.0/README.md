# Liaison v0.2.0 — Full Implementation Specifications

This directory contains the full implementation specifications for Liaison v0.2.0.
Each document covers one subsystem and is the source of truth for that area.

## Document Index

| Document | Subsystem | Lines |
|----------|-----------|-------|
| [VERSION_FREEZE.md](VERSION_FREEZE.md) | Version scope and frozen interfaces | ~80 |
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | Component diagram and data flow | ~180 |
| [RUNTIME_CONFIG_SPEC.md](RUNTIME_CONFIG_SPEC.md) | All config/ YAML files and schemas | ~240 |
| [DUAL_WORKSTATION_PROFILES.md](DUAL_WORKSTATION_PROFILES.md) | DGX-Spark vs EVO-X2 profiles | ~160 |
| [MODEL_ROUTING_AND_BUDGETS.md](MODEL_ROUTING_AND_BUDGETS.md) | Local/remote model routes and budgets | ~160 |
| [EXECUTOR_ADAPTER_CONTRACT.md](EXECUTOR_ADAPTER_CONTRACT.md) | Shell/opencode/codex/claude adapters | ~180 |
| [WORKER_RUNTIME_AND_TASK_QUEUE.md](WORKER_RUNTIME_AND_TASK_QUEUE.md) | Worker run-once, task states, artifacts | ~170 |
| [EVIDENCE_VALIDATION_AND_GATES.md](EVIDENCE_VALIDATION_AND_GATES.md) | Evidence artifacts, validation, gates | ~180 |
| [CONFIDENCE_CALIBRATION_GATE.md](CONFIDENCE_CALIBRATION_GATE.md) | Calibration gate for trading/prediction | ~200 |
| [PROJECT_PORTFOLIO_WORKSTATION_ASSIGNMENT.md](PROJECT_PORTFOLIO_WORKSTATION_ASSIGNMENT.md) | Project-to-host assignment | ~150 |
| [PORTFOLIO_TASK_GENERATION.md](PORTFOLIO_TASK_GENERATION.md) | Task packet generation from registry | ~130 |
| [PORTFOLIO_CLI_INTEGRATION.md](PORTFOLIO_CLI_INTEGRATION.md) | CLI subcommand wiring | ~70 |
| [LOCAL_AGENTS_INTEGRATION_APPENDIX.md](LOCAL_AGENTS_INTEGRATION_APPENDIX.md) | Hub agent integration | ~100 |
| [CODEX_IMPLEMENTATION_PLAN.md](CODEX_IMPLEMENTATION_PLAN.md) | Codex build sequence | ~130 |

## How to Read

1. Start with [VERSION_FREEZE.md](VERSION_FREEZE.md) for scope boundaries
2. Read [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) for the component diagram
3. Dive into individual subsystems as needed

## Relationship to Code

Each spec maps to source files under `src/liaison/` and config files under `config/`.
The specs are the design; the code is the implementation. When they diverge, the
code is authoritative for behavior and the spec is authoritative for intent.

## Status

- Phases 1-8A, 10, 11: **Complete** — code and specs aligned
- Phase 8B (NIM endpoints): **Specified, not implemented** — requires NVIDIA_API_KEY
- Phase 8C (Remote approval): **Specified, not implemented** — depends on 8B
- Phase 9 (ML-Intern sandbox): **Specified, not implemented** — requires ml-intern tool
