# PROJECT_PORTFOLIO_WORKSTATION_ASSIGNMENT — Liaison v0.2.0

## Overview

Projects are assigned to workstations based on compute requirements. The
portfolio registry tracks all projects and their host assignments.

## Portfolio Registry

`config/project_registry.active.yaml` contains 41 registered projects across
two workstations.

### Project Entry Structure

```yaml
projects:
  sigma:
    name: Sigma Trading Platform
    repo: ~/quantumGlobalGroup/sigma
    host: dgx_spark
    tier: A
    phase: alpha
    workflow: sigma-integration
    validation_profile: sigma
    description: Quantum-enhanced trading platform
```

### Registry Files

| File | Purpose |
|------|---------|
| `config/project_registry.active.yaml` | Active projects (41 entries) |
| `config/project_registry.archives.yaml` | Archived projects |
| `config/project_registry.merge_sources.yaml` | Merge source mappings |
| `registry/repos.yaml` | Repo paths and metadata |
| `registry/project_plans.yaml` | Per-project plans, workflows, validation |

## Workstation Assignments

### DGX-Spark (Heavy Compute)

Projects requiring GPU compute, model training, or quantum simulation:

| Project | Type | Phase | Validation |
|---------|------|-------|------------|
| sigma | Trading platform | alpha | sigma |
| quantumGlobalGroup | Quantum benchmarks | prototype | quantum |
| qca | Quantum calibration | alpha | quantum |
| ml-research | ML experiments | prototype | ml-research |
| data-flywheel | Agent optimization | prototype | data-flywheel |
| unsloth-finetune | Model fine-tuning | prototype | python |
| portfolio-optimizer | Strategy backtesting | prototype | portfolio |
| qids-modules | QIDS development | prototype | qids |

### EVO-X2 (Operator Cockpit)

Lightweight projects: documentation, audits, web apps, closeout:

| Project | Type | Phase | Validation |
|---------|------|-------|------------|
| clinical-suite | Healthcare integration | beta | python |
| docuQuery | Document RAG | alpha | rag |
| guardianShield | Security tooling | alpha | security |
| adaptive-graph-rag | Graph RAG | prototype | rag |
| event-market-alpha | Event prediction | prototype | python |
| materialScience | Materials research | prototype | python |
| liaison-agentSystem | This repo | alpha | python |

## Project Tiers

| Tier | Description | Review Frequency |
|------|-------------|-----------------|
| A | Core platform / revenue-generating | Every slice |
| B | Supporting infrastructure | Every milestone |
| C | Experimental / exploratory | On closeout |

## Assignment Config

### `config/project_profiles/dgx_compute_projects.yaml`

192 lines listing DGX-Spark projects with:
- Project key, name, repo path
- Compute requirements (GPU memory, estimated runtime)
- Preferred model routes
- Validation profile
- Phase routing

### `config/project_profiles/evox2_lightweight_projects.yaml`

198 lines listing EVO-X2 projects with:
- Project key, name, repo path
- Light task types (audit, security, release-gap)
- Preferred local model route
- Validation profile

### `config/project_profiles/hybrid_qml_kg.yaml`

31 lines for hybrid quantum/ML/knowledge-graph projects that can run on
either workstation depending on model size.

## CLI Access

```bash
# List all projects
liaison portfolio list

# List by host
liaison portfolio list --host dgx_spark
liaison portfolio list --host evox2_windows

# Counts
liaison portfolio counts
liaison portfolio counts --json

# Validate registry
liaison portfolio validate
liaison portfolio validate --json

# Generate tasks
liaison portfolio generate-tasks --dry-run --limit 6
liaison portfolio generate-tasks --host dgx_spark --limit 3
liaison portfolio generate-tasks --project sigma
```

## Dashboard Integration

The dashboard's project portfolio view shows:
- Project matrix table (all projects × phases)
- Per-project detail panel
- Project intake readiness
- Build corpus summary

The Phase 11 TasksPanel shows:
- Tasks by project (top 10)
- Tasks by priority
- Tasks by type
- Recent task list
