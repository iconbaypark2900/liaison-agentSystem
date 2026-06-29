# DUAL_WORKSTATION_PROFILES — Liaison v0.2.0

## Overview

Liaison operates across two workstation profiles with distinct roles. Each
profile has its own project assignments, available services, and compute
characteristics.

## Workstation Profiles

### EVO-X2 (Windows) — Operator Cockpit

| Attribute | Value |
|-----------|-------|
| Role | `operator_cockpit` |
| Host key | `evox2_windows` |
| Primary use | Liaison control plane, dashboards, light tasks |
| GPU | Consumer-grade (RTX class) |
| Services | Ollama, LiteLLM, LibreChat |

**Local services:**
- Ollama: `http://localhost:11434` — small local models
- LiteLLM: `http://localhost:4000` — unified model proxy
- LibreChat: `http://localhost:3080` — chat UI

**Assigned projects (lightweight):**
- Clinical Suite (sigma-integration)
- docuQuery
- GuardianShield
- Adaptive Graph RAG
- Event Market Alpha
- Material Science
- Frontend/backend web apps
- Documentation and closeout tasks

### DGX-Spark — Heavy Compute

| Attribute | Value |
|-----------|-------|
| Role | `heavy_compute` |
| Host key | `dgx_spark` |
| Primary use | Model training, fine-tuning, benchmarks, quantum |
| GPU | DGX-class (multi-GPU) |
| Services | Ollama, vLLM, SGLang, NIM |

**Local services:**
- Ollama: `http://dgx-spark.local:11434`
- vLLM: `http://dgx-spark.local:8000/v1` — high-throughput inference
- SGLang: `http://dgx-spark.local:8001/v1` — structured generation
- NIM: `http://dgx-spark.local:8002/v1` — NVIDIA inference microservices

**Assigned projects (compute-heavy):**
- Quantum benchmarks (QCA, Ising calibration)
- ML research experiments
- Data flywheel cycles
- Model fine-tuning (Unsloth)
- Portfolio optimization backtests
- QIDS module calibration

## Project Assignment Rules

1. **Light tasks** (documentation, audits, security scans, closeout) → EVO-X2
2. **Compute tasks** (training, benchmarks, calibration) → DGX-Spark
3. **Hybrid tasks** (RAG, knowledge graphs) → either, based on model size
4. **Remote tasks** (NIM endpoints) → DGX-Spark (has NIM service)

## Assignment Config

Project-to-host assignments live in `config/project_profiles/`:

- `dgx_compute_projects.yaml` — 192 lines, DGX-specific projects
- `evox2_lightweight_projects.yaml` — 198 lines, EVO-X2-specific projects
- `hybrid_qml_kg.yaml` — 31 lines, hybrid projects

## Dashboard Integration

The dashboard's `workstation_usage` block shows:
- `profile_defaults` — current host's default settings
- `running_ventures` — active terminal sessions
- `max_active_ventures` — concurrent session limit
- `ventures_free` — available slots

```bash
liaison portfolio list --host dgx_spark
liaison portfolio list --host evox2_windows
liaison portfolio counts --json
```

## Cross-Host Workflow

When a task needs both workstations:

1. EVO-X2: `liaison init` + `liaison snapshot` (planning)
2. DGX-Spark: `liaison worker run-once` (compute)
3. EVO-X2: `liaison evidence show` + `liaison gate evaluate` (review)
4. Either: `liaison close-task` (closeout)

The `.liaison/` state directory is per-host. For cross-host work, evidence
artifacts are transferred manually or via git.

## Network Topology

```
EVO-X2 (Windows)                    DGX-Spark (Linux)
┌──────────────┐                   ┌──────────────┐
│ Ollama :11434│                   │ Ollama :11434│
│ LiteLLM :4000│ ─── network ────► │ vLLM  :8000  │
│ LibreChat    │                   │ SGLang:8001  │
└──────────────┘                   │ NIM   :8002  │
                                   └──────────────┘
```

Both workstations share the same git repo structure. Liaison state (`.liaison/`)
is local to each machine and not shared.
