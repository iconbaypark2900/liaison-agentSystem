# Repo Audit

## Source Repo

`$LIAISON_ROOT`

## Runtime Demo Repo

`~/spark/flow-demos/spark-flow-demo`

## Commit Policy

Commit:

- `bin/`
- `checks/`
- `config/`
- `departments/`
- `policies/`
- `skills/`
- `templates/`
- `workflows/`
- `docs/`
- sanitized `examples/`

Do not commit:

- `.spark-flow/`
- `logs/`
- `.env`
- API keys
- local virtual environments
- temporary task outputs

## Current Safe Rollback Tags

Use:

```bash
git tag --list
```
