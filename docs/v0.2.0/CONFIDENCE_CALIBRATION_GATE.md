# CONFIDENCE_CALIBRATION_GATE — Liaison v0.2.0

## Overview

The confidence calibration gate is a specialized evidence artifact for
trading, prediction, and ML research projects. It ensures that model
predictions are calibrated before any live capital allocation or production
deployment.

## When It Applies

The calibration gate is required for:
- Portfolio optimization strategies
- Trading signal generators
- Prediction models with probability outputs
- Any task declaring `calibration_required_artifacts`

## Required Artifacts

```yaml
calibration_required_artifacts:
  - fabricated_edge_scan.json
  - reliability_report.json
  - confidence_calibration_gate.json
```

### `fabricated_edge_scan.json`

Scans for fabricated or unrealistic edges in backtest results.

```json
{
  "run_id": "20260610T123000Z-...",
  "task_id": "sigma-calibration-gate-001",
  "artifact": "fabricated_edge_scan.json",
  "status": "not_run",
  "fabricated_edge_scan_run": false,
  "fabricated_edges_found": null
}
```

In real execution mode:
- `status`: `passed` or `failed`
- `fabricated_edge_scan_run`: `true`
- `fabricated_edges_found`: count or list of suspicious edges

### `reliability_report.json`

Reports reliability metrics for the strategy/model.

```json
{
  "run_id": "20260610T123000Z-...",
  "task_id": "sigma-calibration-gate-001",
  "artifact": "reliability_report.json",
  "status": "not_run",
  "reliability_analysis_run": false,
  "calibration_metrics": {}
}
```

In real execution mode:
- `status`: `passed` or `failed`
- `reliability_analysis_run`: `true`
- `calibration_metrics`: Brier score, ECE, log loss, etc.

### `confidence_calibration_gate.json`

The gate artifact that blocks or allows progression.

```json
{
  "run_id": "20260610T123000Z-...",
  "task_id": "sigma-calibration-gate-001",
  "artifact": "confidence_calibration_gate.json",
  "status": "blocked",
  "confidence_calibration_passed": false,
  "blockers": [
    "placeholder_worker_did_not_run_calibration",
    "human_review_required"
  ]
}
```

In real execution mode:
- `status`: `passed` or `blocked`
- `confidence_calibration_passed`: `true` if metrics meet thresholds
- `blockers`: empty if passed, list of failure reasons if blocked

## Calibration Policy

Defined in `policies/confidence_calibration.yaml`:

```yaml
version: "0.2.0"
enabled: false
require_human_approval: true
calibration_thresholds:
  brier_score_max: 0.25
  ece_max: 0.10
  log_loss_max: 0.69
minimum_samples: 100
block_on_failure: true
```

## Gate Integration

The promotion gate checks task-specific artifacts for blocking status:

```python
def task_specific_artifact_status_findings(*, run_dir, summary):
    findings = []
    for artifact in summary.get("task_specific_artifacts", []):
        if not name.endswith(".json") or artifact.get("status") == "missing":
            continue
        payload = read_json_file(safe_artifact_path(run_dir, name))
        status = str(payload.get("status", "")).lower()
        if status in {"blocked", "failed"}:
            findings.append({
                "artifact": name,
                "status": status,
                "blocking": True,
                "failed_check": f"task_specific_artifact:{name}:{status}",
            })
    return findings
```

If `confidence_calibration_gate.json` has `status: "blocked"`, the promotion
gate adds it to `failed_checks` and sets the overall gate status to `blocked`.

## Portfolio Optimizer Workflow

The `workflows/portfolio-optimizer.yaml` workflow includes a calibration
phase:

```yaml
- name: risk_review
  route: reviewer
  skills: [risk-management, portfolio-research]
  artifacts:
    - portfolio/risk_report.md
  approval: required

- name: strategy_validate
  kind: deterministic
  validate_profile: portfolio
  approval: required
```

The calibration gate is evaluated during `strategy_validate` and must pass
before `paper_trade` can begin.

## Trading Safety

| Layer | Check | Enforcement |
|-------|-------|-------------|
| Task YAML | `safety.live_allowed: false` | Always false in v0.2.0 |
| Budget | `trading_or_capital_related: max_cost_usd: 0.0` | No hosted model cost |
| Policy | `confidence_calibration.yaml: enabled: false` | Calibration not auto-run |
| Gate | `confidence_calibration_passed: false` | Blocks promotion |
| Human | `required_human_approval: true` | Always required |

**No live capital allocation is possible through Liaison v0.2.0.** The
calibration gate, budget system, and human approval requirements form a
multi-layer defense against premature deployment.

## Future: Real Calibration (v0.3.0+)

When `confidence_calibration.yaml` is enabled:
1. Worker runs calibration script via shell executor
2. Metrics compared against thresholds
3. `confidence_calibration_gate.json` updated with real results
4. Gate evaluation uses real pass/fail
5. Human still required for any live allocation
