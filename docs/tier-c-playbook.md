# Tier C playbook

Short guide for registered repos that are **intake-only** today and how to promote them to Tier B (plan + validation profile).

Parent backlog: [finish-backlog/track-b-portfolio.md](finish-backlog/track-b-portfolio.md) (Track B.3).

---

## What Tier C gets

Tier C repos in `registry/repos.yaml` have `default_profile: none` and **no** entry in `registry/project_plans.yaml`.

| Capability | Tier C |
|------------|--------|
| Rolodex / matrix visibility | Yes |
| `liaison project-intake --show` | Yes (runtime fallback in `project_plans.py`) |
| Operating plan YAML on disk | No (until promoted) |
| Engineering gate commands in dashboard | Generic fallback only |
| Validation profile | None until promoted |
| Walkthrough / executor soft-gate | Intake blockers only |

**Operator action:** Run intake, assess maturity, file blockers. Do not expect Hermes-led slices with project-specific validation until promoted.

```bash
liaison project-intake --project <key> --show
liaison assess-project --show
```

---

## Tier B vs Tier A

| Tier | `project_plans.yaml` | `default_profile` | Typical use |
|------|----------------------|-------------------|-------------|
| **C** | absent | `none` | Registered, intake-only |
| **B** | entry with workflow + pattern | set (e.g. `python`) | Plan on disk; engineering gates defined |
| **A** | full plan + backlog | matched to checks | Wave-1 walkthrough repos (sigma, clinical_suite, …) |

---

## Promote Tier C → Tier B

1. **Intake clean** — `liaison project-intake --project <key> --show` shows no blocking gaps for research phase.
2. **Add plan entry** — Edit `registry/project_plans.yaml`: intent, workflow, pattern, validation_profile, gate commands, backlog stub.
3. **Set profile** — In `registry/repos.yaml`, set `default_profile` to a known checks profile (`python`, `sigma`, `rag`, …).
4. **Bootstrap memory** — In the repo: `liaison init <task-id> "First slice"`; optional `PROJECT_PHASE.md` from `templates/PROJECT_PHASE.md`.
5. **Verify JSON** — `liaison command-center --json --project <key>` shows `project_plan`, intake tiers, and `suggested_workflow_commands` when focused.

Wave-2 bulk promotion: see finish backlog **B.2** (`memory/portfolio_bootstrap.log`).

---

## Tier A wave 1 (reference)

Tier A keys with full plans today: `sigma`, `clinical_suite`, `adaptive_graph_rag`, `research`, `materialScience`.

Bootstrap intake (dry/show):

```bash
./scripts/bootstrap-portfolio-wave1.sh
```
