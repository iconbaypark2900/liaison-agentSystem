# RUNTIME_CONFIG_SPEC — Liaison v0.2.0

## Overview

All runtime configuration lives under `config/` as YAML files. Each file has a
`version` field for forward compatibility. Config files are read at runtime and
never mutated by the worker or CLI.

## Config Files

### `config/hosts.yaml`

Defines the two workstation profiles and their local services.

```yaml
version: 0.2.0
hosts:
  evox2_windows:
    role: operator_cockpit
    services:
      ollama: { url: http://localhost:11434 }
      litellm: { url: http://localhost:4000 }
      librechat: { url: http://localhost:3080 }
  dgx_spark:
    role: heavy_compute
    services:
      ollama: { url: http://dgx-spark.local:11434 }
      vllm: { url: http://dgx-spark.local:8000/v1 }
      sglang: { url: http://dgx-spark.local:8001/v1 }
      nim: { url: http://dgx-spark.local:8002/v1 }
```

| Field | Type | Description |
|-------|------|-------------|
| `role` | str | `operator_cockpit` or `heavy_compute` |
| `services` | map | Service name → URL |

### `config/model_routes.yaml`

Defines local and remote model routes with trigger tags and approval gates.

**Structure:**
- `defaults` — global routing defaults
- `local_models` — Ollama-hosted models (4 routes: stable, coder, patch, reviewer)
- `remote_models` — NVIDIA NIM models (3 routes: deepseek, qwen, nemotron)
- `quantum_models` — Quantum-specific NIM models

Each route declares:
- `provider` — ollama, nvidia_nim
- `model` — model identifier
- `agent` — preferred executor (opencode, codex, claude)
- `use_for` — list of use cases
- `trigger_tags` — hash tags that activate the route
- `requires_human_approval` — bool
- `edits_files` — bool (remote routes are read-only)

**Defaults:**
- `local_first: true` — prefer local models
- `require_human_approval_for_remote: true`
- `remote_outputs_are_read_only: true`
- `local_outputs_require_approval: true`

### `config/budgets.yaml`

Cost budgets per task type and globally.

```yaml
version: 0.2.0
budgets:
  global:
    daily_max_usd: 5.0
    monthly_max_usd: 25.0
    require_approval_above_usd: 0.25
task_type_budgets:
  summarize:     { max_cost_usd: 0.0,  allow_hosted: false }
  code_patch:    { max_cost_usd: 0.5,  allow_hosted: true }
  calibration:   { max_cost_usd: 0.0,  allow_hosted: false, requires_human_approval: true }
  trading_or_capital_related: { max_cost_usd: 0.0, allow_hosted: false, requires_human_approval: true }
```

### `config/executors.yaml`

Executor adapter configuration. Each executor has:

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | bool | Whether the executor is active |
| `type` | str | shell, opencode, codex, claude_code, external_supervisor |
| `command` | str | Binary to invoke |
| `allow_execution` | bool | Whether `run_executor()` is permitted |
| `allow_push` | bool | Whether git push is allowed (always false in v0.2.0) |
| `allow_main_branch` | bool | Whether main branch ops are allowed (always false) |
| `use_litellm_route` | bool | Whether to route through LiteLLM proxy |

**v0.2.0 state:**
- shell: `allow_execution: true` (bash universally available)
- opencode, codex, claude_code: `allow_execution: false` (locked)
- ml_intern: `enabled: false` (disabled)

### `config/validation_profiles.yaml`

Validation profile definitions. Each profile maps to a check script under
`checks/`. Profiles are referenced by project plans and workflow packs.

### `config/worker.yaml`

Worker runtime configuration.

```yaml
queue_root: .liaison/tasks
runs_root: .liaison/runs
max_concurrent_runs: 1
```

### `config/project_profiles/`

Per-host project assignments:
- `dgx_compute_projects.yaml` — DGX-Spark heavy compute projects
- `evox2_lightweight_projects.yaml` — EVO-X2 lightweight projects
- `hybrid_qml_kg.yaml` — Hybrid quantum/ML/knowledge-graph projects

### `config/skill_resolution.yaml`

Maps project plans to workflows and skills. Used by the dashboard to recommend
agents per project phase.

## Config Loading

All config is loaded via `yaml.safe_load()` with error handling:

```python
def load_executor_config(root: Path = Path(".")) -> dict[str, Any]:
    config_path = root / EXECUTOR_CONFIG_PATH
    if not config_path.exists():
        return {"version": "0.2.0", "executors": {}}
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}
```

Missing files return empty defaults. Invalid YAML raises `RuntimeError`.

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `LIAISON_ENV` | Environment label for dashboard | `local` |
| `NVIDIA_API_KEY` | NVIDIA NIM endpoint access (Phase 8B) | — |
| `LIAISON_ROOT` | Project root override | cwd |

## Config Validation

`liaison portfolio validate --json` checks:
- All referenced workflows exist in `registry/workflows.yaml`
- All referenced validation profiles exist in `config/validation_profiles.yaml`
- Project registry entries have required fields
- Host assignments match `config/hosts.yaml`
