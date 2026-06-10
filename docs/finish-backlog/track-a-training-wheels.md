# Track A — Training wheels

**Purpose:** Low-risk operator discipline via Cursor hooks, local digest cron, and E2E smoke. Complements Liaison CLI; does **not** replace `observe-session complete`.

[Index ←](README.md) · **Setup guide:** [operator-training-wheels.md](../operator-training-wheels.md)

---

| ID | Title | Size | Deps | Status | Done when |
|----|--------|------|------|--------|-----------|
| **A.1** | Project hook: session end nudge | S | — | **Done** | `.cursor/hooks.json` on `stop`/`sessionEnd` → `liaison-session-done` reminder |
| **A.2** | Project hook: shell after executor | S | A.1 | **Done** | `afterShellExecution`: hermes/qca/ml_intern → remind complete session |
| **A.3** | Local digest cron (DGX) | S | — | **Done** | `scripts/snapshot-command-center.sh` → `memory/snapshots/latest.json` |
| **A.4** | Cursor Automation: weekday digest | M | A.3 | **Draft (UI)** | [cursor-automations-setup.md](../cursor-automations-setup.md) + [liaison-weekday-digest.yaml](../automation-prefills/liaison-weekday-digest.yaml) |
| **A.5** | Cursor Automation: Tier A PR comments | S | — | **Draft (UI)** | [cursor-automations-setup.md](../cursor-automations-setup.md) + [liaison-tier-a-pr-gate-comment.yaml](../automation-prefills/liaison-tier-a-pr-gate-comment.yaml) |
| **A.6** | E2E operator smoke script | M | — | **Done** | `tests/e2e_operator_smoke.sh` + checklist in [execution-bridge.md](../execution-bridge.md) |

---

## Quick start

```bash
# Verify hooks + snapshot + smoke (one shot)
test -f .cursor/hooks.json && test -x scripts/snapshot-command-center.sh && bash tests/e2e_operator_smoke.sh

# Install snapshot cron (A.3 → A.4)
./scripts/install-snapshot-cron.sh --every-minutes 15

# Cursor automations (A.4, A.5) — see docs/cursor-automations-setup.md

# Example jq on snapshot (queue + stale)
jq '{at:.generated_at, pending:.venture_queue_summary.pending_count, stale:.stale_executor_sessions}' memory/snapshots/latest.json
```

**Artifacts:** `.cursor/hooks.json` · `.cursor/hooks/liaison-session-nudge.sh` · `scripts/snapshot-command-center.sh` · `tests/e2e_operator_smoke.sh` · [cursor-automation-drafts.md](../cursor-automation-drafts.md)

---

## Notes

- **A.4 / A.5** — Repo draft specs only; finish in Cursor UI. Not marked Done until automations are live.
- Hook and snapshot setup: [operator-training-wheels.md](../operator-training-wheels.md).
