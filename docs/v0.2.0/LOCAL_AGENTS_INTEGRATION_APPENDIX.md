# LOCAL_AGENTS_INTEGRATION_APPENDIX — Liaison v0.2.0

## Overview

Liaison integrates with hub agents — local CLI tools that perform specialized
work. This appendix documents the agent registry, handoff chains, and how
Liaison coordinates between agents.

## Hub Agents

Defined in `registry/agents.yaml`:

| Agent | Role | CLI Tool | Status |
|-------|------|----------|--------|
| hermes | Explorer/researcher | hermes | Active |
| ml_intern | ML research worker | ml-intern | Stub (Phase 9) |
| qca | Quantum calibration | qca | Active |
| unsloth_studio | Model fine-tuning | unsloth-studio | Active |
| liaison | Control plane | liaison | Active |
| claude | Code review/planning | claude | Active |
| opencode | Code generation | opencode | Active |
| codex | Patching/debugging | codex | Active |

## Agent Skills

Defined in `registry/skills.yaml` and `registry/hub_skills.yaml`:

| Skill | Owner | Used For |
|-------|-------|----------|
| spark-flow-planning | liaison | Task planning |
| spark-flow-build | liaison | Build phase |
| spark-flow-review | liaison | Code review |
| spark-flow-closeout | liaison | Task closeout |
| testing-hardening | liaison | Validation |
| scientific-validation | liaison | Research validation |
| cudaq-quantum-workflow | qca | Quantum workflows |
| nvidia-ising-review | qca | Ising calibration |
| rag-design | hermes | RAG architecture |
| rag-ingestion | hermes | Corpus preparation |
| ml-research-design | ml_intern | ML experiment design |
| backtest-engineering | unsloth_studio | Strategy backtesting |
| frontend-design | claude | Frontend architecture |
| backend-design | claude | Backend architecture |

## Handoff Chains

Defined in `registry/handoff_chains.yaml` and `dashboard/command_center/data.py`:

| Chain | Agents | When |
|-------|--------|------|
| ML Intern → QCA → Hermes | ml_intern, qca, hermes | Benchmark code → VLM plot review → integrate/PR |
| Unsloth → Hermes deploy | unsloth_studio, hermes | GPU fine-tune/export → vLLM/Ollama compose |
| Hermes → Liaison task | hermes, liaison | Exploratory work → governed vertical slice |
| Liaison plan → build → review → close | claude, opencode | Phase executor lane for one slice |
| Hermes → QCA → Hermes | hermes, qca, hermes | Ising/calibration routing and integration |

## Phase Routing

`registry/phase_routing.yaml` maps task phases to agents:

```yaml
task_phases:
  phases:
    - plan      # → claude (reviewer route)
    - build     # → opencode (coder route)
    - patch     # → codex (patch route)
    - review    # → claude (reviewer route)
    - close     # → opencode (stable route)
```

## Project Phase Routing

```yaml
project_phases:
  prototype:
    validation: optional
    debrief_required: false
  alpha:
    validation: required
    debrief_required: true
  beta:
    validation: required
    debrief_required: true
  mvp:
    validation: required
    debrief_required: true
```

## Liaison as Coordinator

Liaison does not directly invoke hub agents. Instead:

1. **Liaison creates task packets** — YAML files in `.liaison/tasks/backlog/`
2. **Operator assigns to agent** — manually or via dashboard
3. **Agent works in its own terminal** — using its own CLI tool
4. **Agent reports back** — output goes to `outbox/` or task artifacts
5. **Liaison reviews evidence** — `liaison evidence show`, `liaison gate evaluate`
6. **Liaison governs promotion** — human approval required

This separation ensures Liaison never directly executes agent code, maintaining
the safety boundary.

## Dashboard Integration

The dashboard shows:
- **Agent hub list** — all registered agents with status and skills
- **Handoff chains** — visual representation of agent sequences
- **Recommended agents** — per project phase, based on routing
- **Rolodex** — categorized view of agents, skills, and projects

## Spark-Flow Bridge

The dashboard and CLI communicate with `bin/spark-flow` via a dynamic import:

```python
def _bridge():
    global _spark_flow
    if _spark_flow is None:
        from importlib.machinery import SourceFileLoader
        path = AGENT_SYSTEM_DIR / "bin" / "spark-flow"
        _spark_flow = SourceFileLoader("spark_flow_bridge", str(path)).load_module()
    return _spark_flow
```

This bridge provides:
- `collect_look_state()` — aggregated control plane state
- `parse_registry_map()` — registry YAML loading
- `build_project_matrix()` — project cross-reference
- `parse_phase_routing()` — phase routing config
- `parse_validation_profiles()` — validation profiles

## Workflow Pack Integration

Each workflow pack (Phase 10) declares agent routes per phase:

```yaml
phases:
  - name: rag_plan
    route: reviewer        # → claude
    skills: [spark-flow-planning, rag-design]
    approval: required
```

The `route` field maps to an agent via `PHASE_ROUTE_AGENTS`:

```python
PHASE_ROUTE_AGENTS = {
    "plan": "claude",
    "build": "opencode",
    "patch": "codex",
    "review": "claude",
    "close": "opencode",
}
```
