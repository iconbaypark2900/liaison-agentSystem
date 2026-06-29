# MODEL_ROUTING_AND_BUDGETS — Liaison v0.2.0

## Overview

Liaison routes model calls through a layered system: local models first, remote
models only with human approval, and all calls subject to budget limits.

## Routing Principles

1. **Local first** — prefer Ollama-hosted models on the operator's workstation
2. **Remote requires approval** — NIM endpoints need explicit human sign-off
3. **Remote is read-only** — remote models never edit files directly
4. **Budgets are enforced** — per-task and global cost limits apply
5. **Trigger tags activate routes** — hash tags in task text select models

## Local Model Routes

| Route | Provider | Model | Agent | Use Cases |
|-------|----------|-------|-------|-----------|
| stable | ollama | qwen3.6:latest | opencode | closeout, docs, small edits, summaries |
| coder | ollama | qwen3-coder:30b | opencode | implementation, tests, bugfixes, refactors |
| patch | ollama | gpt-oss:20b | codex | minimal patches, test failures, targeted fixes |
| reviewer | ollama | nemotron-3-nano:30b | claude | planning, review, risk, architecture |

Local models have no cost and no approval requirement. They are the default
for all v0.2.0 operations.

## Remote Model Routes (NVIDIA NIM)

| Route | Model | Use Cases | Trigger Tags |
|-------|-------|-----------|--------------|
| deepseek_v4_flash | deepseek-ai/deepseek-v4-flash | long-context coding, repo-wide analysis | #deepseek #long_context #repo_wide |
| qwen3_coder_480b | qwen/qwen3-coder-480b-a35b | large coding plans, multi-file refactors | #big_refactor #coding_plan |
| nemotron_ultra_550b | nvidia/nemotron-3-ultra-550b | architecture review, strategic reasoning | #planning #architecture #strategic |

**Remote route constraints:**
- `requires_human_approval: true` — always
- `edits_files: false` — always (read-only)
- Requires `NVIDIA_API_KEY` environment variable
- Outputs go to `outbox/` only

## Quantum Model Routes

| Route | Model | Use Cases | Trigger Tags |
|-------|-------|-----------|--------------|
| ising_calibration | nvidia/ising-calibration-1-35b-a3b | quantum calibration plot analysis | #ising #calibration #qec_plots |

Quantum routes follow the same remote constraints as other NIM routes.

## Budget System

### Global Budgets

```yaml
budgets:
  global:
    daily_max_usd: 5.0
    monthly_max_usd: 25.0
    require_approval_above_usd: 0.25
```

Any single call exceeding $0.25 requires human approval.

### Per-Task-Type Budgets

| Task Type | Max Cost | Hosted Allowed | Human Approval |
|-----------|----------|----------------|----------------|
| summarize | $0.00 | no | — |
| code_patch | $0.50 | yes | if > $0.25 |
| calibration | $0.00 | no | always |
| trading_or_capital_related | $0.00 | no | always |

Calibration and trading tasks have zero budget — they cannot use hosted models
at all and always require human approval.

## Route Selection Logic

```
1. Parse task text for trigger tags (#deepseek, #ising, etc.)
2. If tags match a remote route:
   a. Check NVIDIA_API_KEY presence
   b. Check budget remaining
   c. Check human approval status
   d. If all pass → route to remote (read-only)
   e. If any fail → fall back to local
3. If no remote tags:
   a. Match task type to local route use_for list
   b. Route to matching local model
   c. Default to "stable" route if no match
```

## Budget Enforcement

Budgets are checked before any model call:

```python
def check_budget(task_type: str, estimated_cost: float) -> tuple[bool, str]:
    budget = task_type_budgets.get(task_type, {})
    max_cost = budget.get("max_cost_usd", 0.0)
    if estimated_cost > max_cost:
        return False, f"Estimated ${estimated_cost} exceeds ${max_cost} for {task_type}"
    if estimated_cost > require_approval_above_usd:
        return False, "Human approval required"
    return True, "OK"
```

## Dashboard Budget Panel

The BudgetsPanel (Phase 11) shows:
- Configured limits (per-run and per-day)
- Recent run spend indicators (models_called, executors_called, shell_commands)
- Budget currency (USD)

## v0.2.0 Status

- Local model routes: **Active** (via Ollama)
- Remote model routes: **Specified, not wired** (Phase 8B — requires NVIDIA_API_KEY)
- Budget enforcement: **Specified, not wired** (Phase 8B)
- Dashboard budget display: **Active** (Phase 11)
