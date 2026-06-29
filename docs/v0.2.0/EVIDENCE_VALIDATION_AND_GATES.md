# EVIDENCE_VALIDATION_AND_GATES — Liaison v0.2.0

## Overview

Every worker run produces a complete evidence folder under
`.liaison/runs/<run-id>/`. The evidence is reviewed by a human operator before
any promotion decision. The promotion gate evaluates the evidence and reports
pass/fail status.

## Evidence Folder Structure

```
.liaison/runs/20260610T123000Z-clinical-suite-clinical-suite-audit-001/
├── task.yaml                          # Task packet copy
├── context.md                         # Run context
├── command.txt                        # Commands executed
├── model_calls.jsonl                  # Model call log
├── executor_result.json               # Executor output
├── stdout.log                         # Captured stdout
├── stderr.log                         # Captured stderr
├── patch.diff                         # Generated patch
├── validation.log                     # Validation results (YAML)
├── validation_result.json             # Pass/fail summary
├── validation_result.md              # Human-readable result
├── validation_plan.json               # Planned validation commands
├── validation_plan.md                 # Plan in markdown
├── validation_execution_approval.json # Approval state
├── validation_execution_approval.md  # Approval doc
├── security.log                       # Security check results
├── data_quality.log                   # Data quality check
├── compliance.md                      # Compliance evidence
├── debrief.md                         # Run debrief
├── promotion_gate.json                # Gate status
└── run_metadata.json                  # Run metadata
```

## Validation Profiles

Validation profiles are defined in `config/validation_profiles.yaml` and
referenced by project plans and workflow packs.

| Profile | Check Script | Purpose |
|---------|-------------|---------|
| python | checks/python.sh | Python projects (pytest + compileall) |
| rag | checks/rag.sh | RAG apps (retrieval eval files) |
| quantum | checks/quantum.sh | Quantum benchmarks (config + results) |
| ml-research | checks/ml-research.sh | ML research (experiment + metrics) |
| frontend | checks/frontend.sh | Frontend apps (lint + test + build) |
| backend | checks/backend.sh | Backend services (pytest + openapi) |
| security | checks/security.sh | Security scan (secrets + gitignore) |
| sigma | checks/sigma.sh | Sigma platform (liaison doctor + tests) |
| ai-app | checks/ai-app.sh | AI applications |
| data-flywheel | checks/data-flywheel.sh | Data flywheel cycles |
| sampling | checks/sampling.sh | Sampling validation |

## Validation Execution Flow

### Placeholder Mode (default)

When `policies/validation_execution.yaml` has `enabled: false`:

1. Validation commands are **planned** but not executed
2. `validation.log` marks all entries as `status: skipped`
3. `validation_result.json` has `status: not_run`, `evidence_only: true`
4. `executor_result.json` has `executed: false`
5. Promotion gate status: `review_required`

### Real Execution Mode

When policy is `enabled: true` (and approval granted):

1. Each validation command runs via `run_executor("shell", ["-c", cmd])`
2. Results captured: exit_code, stdout, stderr, duration
3. `validation.log` records real results per command
4. `validation_result.json` has `status: passed|failed`, `evidence_only: false`
5. Security check runs `checks/security.sh` in repo directory
6. Promotion gate updated with real pass/fail

## Promotion Gate

### Gate Structure

```json
{
  "run_id": "20260610T123000Z-...",
  "task_id": "clinical-suite-audit-001",
  "project": "clinical-suite",
  "status": "review_required",
  "live_allowed": false,
  "customer_release_allowed": false,
  "production_allowed": false,
  "required_human_approval": true,
  "validation_passed": false,
  "security_passed": true,
  "data_quality_passed": false,
  "compliance_passed": false,
  "confidence_calibration_passed": false,
  "failed_checks": ["executor_not_run", "validation_not_run", ...],
  "passed_checks": ["required_artifacts_created", "no_model_calls", ...],
  "missing_evidence": [],
  "notes": ["Safe placeholder worker only; no tools were executed."]
}
```

### Gate Evaluation

`liaison gate evaluate <run-id>`:

1. Read all artifacts from the run directory
2. Check for missing required artifacts
3. Check task-specific artifacts for blocking status
4. Compute gate status:
   - `blocked` — missing evidence or blocking task-specific findings
   - `review_required` — all artifacts present, awaiting human review
   - `passed` — all validation and security checks passed (real mode only)
5. Write updated `promotion_gate.json`

### Gate Status Values

| Status | Meaning | Production Allowed |
|--------|---------|-------------------|
| `review_required` | Artifacts complete, needs human review | No |
| `blocked` | Missing evidence or blocking findings | No |
| `passed` | All checks passed (real execution mode) | No (still needs approval) |

**Note:** Production, customer release, and live flags are **always false** in
v0.2.0. The gate never auto-promotes.

## Evidence Commands

### `liaison evidence show <run-id>`

Displays artifact status for a run:
- Which artifacts are present, missing, or not_applicable
- Task-specific artifact groups
- Promotion gate summary
- Missing evidence count

### `liaison gate evaluate <run-id>`

Evaluates and updates the promotion gate:
- Reads all artifacts
- Checks for missing evidence
- Checks task-specific artifact statuses
- Writes updated `promotion_gate.json`
- Returns exit code 0 if not blocked, 1 if blocked

## Task-Specific Artifacts

Tasks can declare additional required artifacts via:

```yaml
calibration_required_artifacts:
  - fabricated_edge_scan.json
  - reliability_report.json
  - confidence_calibration_gate.json
security_required_artifacts:
  - security_scan_report.json
release_required_artifacts:
  - release_notes.md
research_required_artifacts:
  - experiment_summary.json
```

These artifacts are task-specific and their presence is checked by the gate.

## Human Approval Flow

```
1. Worker run completes → task in review_required
2. Operator reviews: liaison evidence show <run-id>
3. Operator evaluates: liaison gate evaluate <run-id>
4. If gate is "passed" and operator approves:
   - Manually move task to done
   - Manually approve production/customer/live (external to Liaison)
5. If gate is "blocked":
   - Fix missing evidence
   - Re-run gate evaluation
6. If gate is "review_required":
   - Human decides to approve or reject
   - No auto-promotion in v0.2.0
```

## Quality Gates in Workflow Packs

Each workflow pack (Phase 10) declares `quality_gates.required` — a list of
conditions that must be met before the workflow can proceed to the next phase.
These are documented in the workflow YAML and reviewed by the operator, but
not automatically enforced by the gate evaluator in v0.2.0.
