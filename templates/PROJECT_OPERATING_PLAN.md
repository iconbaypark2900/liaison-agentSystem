# Project operating plan: {{PROJECT_KEY}}

Generated: {{GENERATED_AT}}

Repo: `{{REPO_PATH}}`

## Intent

{{INTENT}}

## Maturity target

{{MATURITY_TARGET}}

## Workflow and pattern

| Field | Value |
|-------|-------|
| Workflow | {{WORKFLOW}} |
| Workflow source | {{WORKFLOW_SOURCE}} |
| Pattern | {{PATTERN}} |
| Validation profile | {{VALIDATION_PROFILE}} |
| External guide | {{EXTERNAL_GUIDE}} |

## Research gate

{{RESEARCH_GATE_SUMMARY}}

**Commands**

{{RESEARCH_GATE_COMMANDS}}

## Engineering gate

{{ENGINEERING_GATE_SUMMARY}}

**Commands**

{{ENGINEERING_GATE_COMMANDS}}

## Backlog

{{BACKLOG}}

## Intake snapshot

- Intake ready: {{INTAKE_READY}}
- Ready to build: {{READY_TO_BUILD}}
- Recommended lane: {{RECOMMENDED_LANE}}

Refresh with:

```bash
liaison plan-project --project {{PROJECT_KEY}} --write
liaison project-intake --project {{PROJECT_KEY}} --show
```
