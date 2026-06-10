# Track B — Portfolio & walkthrough readiness

**Purpose:** Bootstrap Tier A/C repos on disk, document Tier C ops, audit workflows, and sign off a two-project walkthrough (sigma + clinical_suite).

[Index ←](README.md) · **Tier C guide:** [tier-c-playbook.md](../tier-c-playbook.md)

---

| ID | Title | Size | Deps | Status | Done when |
|----|--------|------|------|--------|-----------|
| **B.1** | Portfolio bootstrap wave 1 | M | — | **Done** | `scripts/bootstrap-portfolio-wave1.sh` — Tier A `project-intake --show` |
| **B.2** | Portfolio bootstrap wave 2 | L | B.1 | **Done** | `scripts/bootstrap-portfolio-wave2.sh` — Tier C intake; `memory/portfolio_bootstrap.log` |
| **B.3** | Tier C playbook | S | — | **Done** | [tier-c-playbook.md](../tier-c-playbook.md) |
| **B.4** | Workflow YAML audit | M | — | **Done** | [workflow-yaml-audit.md](../workflow-yaml-audit.md) |
| **B.5** | Two-project walkthrough sign-off | S | A.6, B.1 | **Ready for human sign-off** | Operator completes [walkthrough-signoff-sigma-clinical.md](../walkthrough-signoff-sigma-clinical.md) |

---

## Quick start

```bash
# Tier A intake (wave 1)
bash scripts/bootstrap-portfolio-wave1.sh

# Tier C intake (wave 2) — appends memory/portfolio_bootstrap.log
bash scripts/bootstrap-portfolio-wave2.sh

# Dry operator smoke (includes wave 1)
bash tests/e2e_operator_smoke.sh

# B.5 automated preflight + human checklist
bash scripts/b5-walkthrough-preflight.sh
# → docs/walkthrough-signoff-sigma-clinical.md
```

**Docs:** [workflow-yaml-audit.md](../workflow-yaml-audit.md) · [walkthrough-signoff-sigma-clinical.md](../walkthrough-signoff-sigma-clinical.md) · [tier-c-playbook.md](../tier-c-playbook.md) · Track A [operator-training-wheels.md](../operator-training-wheels.md)

---

## Cross-links

| Ticket | Command / doc |
|--------|----------------|
| B.1 | `bash scripts/bootstrap-portfolio-wave1.sh` |
| B.2 | `bash scripts/bootstrap-portfolio-wave2.sh` · log: `memory/portfolio_bootstrap.log` |
| B.3 | [tier-c-playbook.md](../tier-c-playbook.md) |
| B.4 | [workflow-yaml-audit.md](../workflow-yaml-audit.md) |
| B.5 | [walkthrough-signoff-sigma-clinical.md](../walkthrough-signoff-sigma-clinical.md) · requires A.6 smoke green |
