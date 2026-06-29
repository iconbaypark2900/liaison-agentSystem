# CODEX_IMPLEMENTATION_PLAN — Liaison v0.2.0

## Overview

This document outlines the implementation sequence for completing the Liaison
v0.2.0 control plane using Codex (or equivalent coding agents). It is ordered
by dependency: each step builds on the previous one.

## Implementation Sequence

### Step 1: Executor Enablement ✅ Complete

**Files:** `src/liaison/executors.py`, `config/executors.yaml`

- Add `ExecutorResult` dataclass
- Implement `run_executor()` with subprocess, timeout, cwd, env
- Add `allow_execution` config field (shell: true)
- Add `cmd_executor_run()` CLI handler
- Register `run` subcommand

**Verification:**
```bash
liaison executor ping shell  # execution_allowed: true
liaison executor run shell -- echo ok  # exit 0, stdout "ok"
pytest tests/test_executor_adapters.py  # 24 pass
```

### Step 2: Worker Real Validation ✅ Complete

**Files:** `src/liaison/worker.py`, `policies/validation_execution.yaml`

- Add `validate_with_executor()` overlay function
- Run validation commands via `run_executor("shell", ...)`
- Run `checks/security.sh` via shell executor
- Overwrite placeholder artifacts with real output
- Update `WorkerRunResult` with execution flags
- Gate execution by policy + human approval

**Verification:**
```bash
# Placeholder mode (default)
pytest tests/test_worker_run_once.py  # 9 pass

# Real mode
cat > policies/validation_execution.yaml << 'EOF'
enabled: true
require_human_approval: false
EOF
liaison worker run-once --project sigma  # real validation.log
```

### Step 3: Unified CLI ✅ Complete

**Files:** `src/liaison/cli.py`, `src/liaison/portfolio.py`

- Build root parser in `cli.py` with `--version`, `--root`
- Register all 5 subcommand groups
- `portfolio.build_parser()` delegates to `cli.build_root_parser()`
- Add `tests/test_cli.py` (10 tests)

**Verification:**
```bash
liaison --help  # shows all 5 subcommands
liaison --version  # liaison 0.2.0
pytest tests/test_cli.py  # 10 pass
```

### Step 4: Workflow Packs ✅ Complete

**Files:** `workflows/*.yaml`, `registry/workflows.yaml`

- Create 8 workflow YAML files (rag-app, quantum-benchmarks, ml-research,
  frontend-app, backend-app, scientific-paper, portfolio-optimizer, qids)
- Index in `registry/workflows.yaml`
- Update `docs/workflow-yaml-audit.md`

**Verification:**
```bash
python -c "import yaml; [yaml.safe_load(open(f'workflows/{w}.yaml')) for w in ['rag-app','quantum-benchmarks','ml-research','frontend-app','backend-app','scientific-paper','portfolio-optimizer','qids']]"
```

### Step 5: Dashboard Panels ✅ Complete

**Files:** `dashboard/command_center/panels.py`, `dashboard/command_center/data.py`,
`dashboard/web/src/components/*.tsx`

- Create 7 panel data helpers in `panels.py`
- Wire into `collect_command_center_state()`
- Create 7 React components
- Add `tests/test_dashboard_panels.py` (14 tests)

**Verification:**
```bash
pytest tests/test_dashboard_panels.py  # 14 pass
```

### Step 6: Documentation ✅ Complete

**Files:** `docs/v0.2.0/*.md`

- Create 15 specification documents
- This document is the last one

### Step 7: Remote NIM Execution (Phase 8B) 🔲 Blocked

**Requires:** `NVIDIA_API_KEY` environment variable

**Files to modify:** `src/liaison/remote.py` (new), `config/model_routes.yaml`

- Implement `run_nim_endpoint()` with capability/provider validation
- Add budget check before remote calls
- Gate behind approved remote request
- Output to `outbox/` only
- Log to JSONL

### Step 8: Remote Result Approval (Phase 8C) 🔲 Blocked

**Requires:** Phase 8B complete

**Files to modify:** `src/liaison/remote.py`, `src/liaison/worker.py`

- Add approval state machine for remote results
- Promote artifacts from `outbox/` to `runs/` only after approval
- Update promotion gate with remote result status

### Step 9: ML-Intern Sandbox (Phase 9) 🔲 Blocked

**Requires:** `ml-intern` CLI tool installed

**Files to modify:** `src/liaison/executors.py`, `config/executors.yaml`

- Enable `ml_intern` executor with `allow_execution: true`
- Add sandbox-only enforcement (no publishing, no private-data upload)
- Wire `research-run --real` command

## Test Strategy

### Unit Tests
- `tests/test_executor_adapters.py` — 24 tests
- `tests/test_worker_run_once.py` — 9 tests
- `tests/test_cli.py` — 10 tests
- `tests/test_dashboard_panels.py` — 14 tests
- `tests/test_portfolio_cli.py` — 7 tests
- `tests/test_portfolio_task_generation.py` — full generation suite

### Integration Tests
- `tests/test_evidence_gate.py` — evidence + gate evaluation
- `tests/test_command_center_app.py` — TUI mount test

### Smoke Tests
```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/ -q
# Expected: 190+ passed, 2 pre-existing failures
```

## Pre-Existing Test Failures

Two tests fail and are accepted as pre-existing:

1. `tests/test_project_plans.py::test_tier_c_fallback` — tier classification
   mismatch (data issue, not code issue)
2. `tests/test_rolodex.py::test_rolodex_skills_from_all_hub_members` — expects
   "liaison" in hub members (registry data issue)

These do not affect v0.2.0 functionality and are tracked for future fix.

## Commit Hygiene

- One logical change per commit
- Commit message format: imperative mood, first line ≤ 72 chars
- Include "why" in the body, not just "what"
- Never commit `.liaison/` runtime state
- Never commit secrets, `.env`, or API keys

## Definition of Done (v0.2.0)

- [x] Executor enablement (shell)
- [x] Worker real validation
- [x] Unified CLI
- [x] 8 workflow packs
- [x] 7 dashboard panels
- [x] 15 specification documents
- [x] 190+ tests passing
- [x] ROADMAP.md updated
- [ ] Phase 8B (blocked on NVIDIA_API_KEY)
- [ ] Phase 8C (blocked on 8B)
- [ ] Phase 9 (blocked on ml-intern tool)
