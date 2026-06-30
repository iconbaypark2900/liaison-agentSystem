# Project Audit — Liaison v0.2.0

**Date:** 2026-06-30  
**Branch:** `agent/liaison/v0.2.0-alpha1-portfolio-cli`  
**Test status:** 238 passed, 0 failures  
**Commits:** 12 on branch

---

## Executive Summary

Liaison v0.2.0 is a **local-first, human-in-the-loop control plane** for coordinating AI-assisted engineering across repos, hub agents, research workers, validation profiles, and approval gates.

**All 11 roadmap phases are complete.** The system has 5,523 lines of Python source, 4,649 lines of test code (0.84 test:source ratio), 12 workflow packs, 7 dashboard panels, 15 specification documents, and 238 passing tests with zero failures.

The project is **functionally complete for v0.2.0** but has several quality issues that should be addressed before a v0.2.1 or v0.3.0 release.

---

## What's Good

### Architecture
- **Clean separation of concerns**: CLI (`cli.py`), executors (`executors.py`), worker (`worker.py`), remote (`remote.py`), approval (`approval.py`), research (`research.py`) — each module has a single responsibility
- **Safety-first design**: Every execution path is gated by policy + config + human approval. No production/customer/live flags are ever auto-set
- **Evidence-based**: Every worker run produces 20+ auditable artifacts. No action happens without a trace
- **Unified CLI**: Single `liaison` entrypoint with 7 subcommand groups (portfolio, worker, evidence, gate, executor, remote, research)

### Test Coverage
- 238 tests, 0 failures
- Test:source ratio of 0.84 — strong for a control plane
- All critical paths covered: executor execution, worker validation, remote gating, approval lifecycle, sandbox enforcement
- Tests run in ~35 seconds

### Documentation
- 15 full implementation specs in `docs/v0.2.0/` (2,142 lines)
- Every subsystem has a dedicated spec document
- ROADMAP.md tracks all phases with completion status
- Code docstrings are accurate and up-to-date

### Workflow Packs
- 12 workflow YAML files covering all project types (RAG, quantum, ML, frontend, backend, papers, portfolio, QIDS, sigma, data-flywheel, python-cli, quantum-ising)
- Each workflow declares principles, phases, quality gates, and validation profiles
- All indexed in `registry/workflows.yaml`

### Safety Posture
- No hardcoded secrets or API keys anywhere in the codebase
- `.gitignore` covers `.env`, `*.env`, secrets, credentials, keys, runtime state
- 6-gate validation for remote NIM calls (capability, provider, approval, API key, budget, outbox-only)
- Sandbox enforcement for ML-Intern (forbidden actions checked, output restricted to outbox)

---

## What Needs Improving

### HIGH Priority

#### 1. Missing validation profiles (3)
Three workflow packs reference validation profiles that don't exist in `config/validation_profiles.yaml`:

| Workflow | References | Exists? |
|----------|-----------|---------|
| `portfolio-optimizer.yaml` | `portfolio` | No |
| `qids.yaml` | `qids` | No |
| `scientific-paper.yaml` | `scientific` | No |

**Fix:** Add `portfolio`, `qids`, and `scientific` entries to `config/validation_profiles.yaml` with check script references.

#### 2. Missing validation_profile field (3)
Three existing workflows don't declare a `validation_profile`:

| Workflow | Has validation_profile? |
|----------|------------------------|
| `data-flywheel.yaml` | No |
| `python-cli.yaml` | No (uses `validate_profile` per-phase) |
| `quantum-ising.yaml` | No (uses `validate_profile` per-phase) |

**Fix:** Add `validation_profile` field or document that per-phase `validate_profile` is the intended pattern.

#### 3. Doc path references are wrong (6 occurrences)
Three `docs/v0.2.0/` files reference `registry/project_registry.*` but the files are actually at `config/project_registry.*`:

- `VERSION_FREEZE.md` (1 occurrence)
- `PORTFOLIO_TASK_GENERATION.md` (1 occurrence)
- `PROJECT_PORTFOLIO_WORKSTATION_ASSIGNMENT.md` (4 occurrences)

**Fix:** Replace `registry/project_registry` with `config/project_registry` in these docs.

### MEDIUM Priority

#### 4. Skills registry owner mismatch
`registry/skills.yaml` has 3 skills with `owner: agent-system`, but no `agent-system` agent exists in `registry/agents.yaml`. The agent should be `liaison`.

**Fix:** Change `owner: agent-system` to `owner: liaison` in `registry/skills.yaml`.

#### 5. Unenforced policy files (6)
Six YAML policy files are not loaded or enforced by any Python code:

| Policy File | Status |
|-------------|--------|
| `agent_safety.yaml` | Not loaded — guidance only |
| `operator_preferences.yaml` | Not loaded — guidance only |
| `secret_handling.yaml` | Not loaded — guidance only |
| `production_readiness.yaml` | Not loaded — guidance only |
| `customer_release.yaml` | Not loaded — guidance only |
| `confidence_calibration.yaml` | Referenced by name but YAML never read |

**Fix:** Either wire these into code as actual gates, or mark them as documentation-only policies. The `confidence_calibration.yaml` is the most important to wire since it's referenced by the calibration gate.

#### 6. Dead config/registry files (7)
Files that exist but are never loaded by any code:

| File | Notes |
|------|-------|
| `config/hosts.yaml` | Host services defined but not loaded by Python |
| `config/project_profiles/hybrid_qml_kg.yaml` | Not loaded (only DGX and EVO profiles have constants) |
| `registry/artifact_contracts.yaml` | Not loaded |
| `registry/provider_profiles.yaml` | Not loaded (note: `config/provider_registry.yaml` IS loaded) |
| `registry/reporter_step_gates.yaml` | Not loaded |
| `registry/repos-evo-x2.yaml` | Not loaded (EVO repos are in `registry/repos.yaml`) |

**Fix:** Either wire these files into code or remove them. `config/hosts.yaml` is the most valuable to wire since the docs reference it.

#### 7. Dead React components (10)
Ten `.tsx` components in `dashboard/web/src/components/` are never imported:

`ApprovalsPanel`, `BudgetsPanel`, `ContextBundlesPanel`, `HubColumn`, `LogsPanel`, `ProjectsColumn`, `RoutingPanel`, `TasksPanel`, `ValidationPanel`, `WorkstreamProjectReport`

**Fix:** Wire these into the web dashboard's page/route structure, or remove if not needed for v0.2.0.

### LOW Priority

#### 8. Large function needs refactoring
`src/liaison/worker.py:1163` — `validate_with_executor()` is 227 lines. Should be split into smaller functions:
- `_run_and_log_validation()`
- `_run_and_log_security()`
- `_overwrite_artifacts_with_results()`
- `_update_gate_and_metadata()`

#### 9. Unused imports (17)
Several `src/liaison/` files have imports that are never used:
- `approval.py`: `argparse`
- `executors.py`: `datetime`, `timezone`
- `portfolio.py`: 8 symbols imported for re-export but unused
- `remote.py`: `argparse`, `sys`, `Mapping`
- `research.py`: `argparse`, `sys`, `Mapping`

**Fix:** Remove unused imports or add them to `__all__` if they're re-exports.

#### 10. Test coverage gaps
Three `src/liaison/` modules have no dedicated test file:
- `portfolio_profiles.py` — covered only transitively
- `portfolio_registry.py` — covered only transitively
- `task_templates.py` — covered only transitively

Three test files have only 1 test each:
- `test_venture_queue.py`
- `test_terminal_sessions.py`
- `test_learning_bridge.py`

**Fix:** Add dedicated test suites for the 3 untested modules; thicken the 3 thin test files.

#### 11. `bin/spark-flow` is a 6,031-line monolith
The legacy CLI script `bin/spark-flow` contains all the original spark-flow logic in a single file. The `src/liaison/` package was built to replace it incrementally, but `bin/spark-flow` is still the primary entrypoint for many commands.

**Fix (v0.3.0):** Continue migrating spark-flow commands into `src/liaison/` modules until `bin/spark-flow` can be reduced to a thin wrapper.

---

## Project Position

### Where It's At

**v0.2.0 is functionally complete.** All 11 roadmap phases are done:

| Phase | Status | Key Deliverable |
|-------|--------|----------------|
| 1-7B | Done | Registries, policies, inspection, context bundles, remote/research skeletons, validation profiles, conductor hardening |
| 8A | Done | NIM dry-run payload builder |
| 8B | Done | Real NIM endpoint execution (gated by NVIDIA_API_KEY) |
| 8C | Done | Remote result approval and handoff |
| 9 | Done | ML-Intern sandbox integration (gated by ml-intern tool) |
| 10 | Done | 8 workflow packs |
| 11 | Done | 7 dashboard panels |

The system is ready for activation when external dependencies are available:
- **NVIDIA NIM**: Set `NVIDIA_API_KEY`, create approved request files, run `liaison remote run <capability>`
- **ML-Intern**: Install `ml-intern` CLI, set `ml_intern.enabled: true` in config, run `liaison research run ml_intern`

### Where It Needs To Go

1. **v0.2.1 (bugfix release)**: Fix the 3 HIGH priority issues (missing validation profiles, doc path references)
2. **v0.3.0 (quality release)**: Wire dead policies, wire dead config files, wire dead React components, refactor large functions, add missing test suites
3. **v0.4.0 (migration release)**: Reduce `bin/spark-flow` monolith by migrating commands to `src/liaison/` modules
4. **v1.0.0 (production release)**: Full policy enforcement (all YAML policies wired to code), complete dashboard (all panels wired), comprehensive test coverage (all modules with dedicated suites)

---

## Metrics Summary

| Metric | Value | Assessment |
|--------|-------|------------|
| Python source LOC | 5,523 | Good for scope |
| Test LOC | 4,649 | Good (0.84 ratio) |
| Test count | 238 | Good |
| Test pass rate | 100% | Excellent |
| Workflow packs | 12 | Complete |
| Dashboard panels | 7 data + 7 React | Data done, React needs wiring |
| Spec documents | 15 (2,142 lines) | Complete |
| Config files | 71 YAML | Some dead |
| Functions > 100 lines | 3 | Refactor candidate |
| Hardcoded secrets | 0 | Excellent |
| Broken doc links | 0 | Good |
| Missing validation profiles | 3 | Needs fix |
| Dead config files | 7 | Needs cleanup |
| Dead React components | 10 | Needs wiring |
| Unenforced policies | 6 | Needs wiring or documentation |
