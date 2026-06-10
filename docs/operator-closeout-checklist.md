# Operator closeout checklist (A.3–A.5 + B.5)

One page for items that **cannot** be finished by git commits alone. Repo helpers are already in tree.

---

## A.3 — Snapshot cron on DGX

```bash
cd /path/to/liaison_agentSystem
./scripts/install-snapshot-cron.sh --every-minutes 15   # already run if crontab shows liaison marker
./scripts/snapshot-command-center.sh                      # manual refresh
tail -f memory/snapshots/cron.log                         # optional
```

- [ ] Crontab contains `# liaison-agentSystem snapshot (A.3)`
- [ ] `memory/snapshots/latest.json` updates every 15 min

---

## A.4 — Cursor: weekday digest

**Guide:** [cursor-automations-setup.md](cursor-automations-setup.md)  
**Prefill:** [automation-prefills/liaison-weekday-digest.yaml](automation-prefills/liaison-weekday-digest.yaml)

- [ ] Automation created in Cursor → Automations
- [ ] Cron: weekdays 08:00 (your timezone)
- [ ] Test run reads `memory/snapshots/latest.json` and lists stale sessions / queue / blockers
- [ ] Mark **A.4 Done** in [track-a-training-wheels.md](finish-backlog/track-a-training-wheels.md)

---

## A.5 — Cursor: Tier A PR comment

**Prefill:** [automation-prefills/liaison-tier-a-pr-gate-comment.yaml](automation-prefills/liaison-tier-a-pr-gate-comment.yaml)

- [ ] Git trigger: PR **opened**
- [ ] Repos scoped to Tier A (`sigma`, `clinical_suite`, `adaptive_graph_rag`, `research`, `materialScience`)
- [ ] Tool: PR comment enabled
- [ ] Test PR receives engineering gate bash block (copy-only)
- [ ] Mark **A.5 Done** in [track-a-training-wheels.md](finish-backlog/track-a-training-wheels.md)

---

## B.5 — Live walkthrough (sigma + clinical_suite)

**Preflight (automated):**

```bash
bash scripts/b5-walkthrough-preflight.sh
```

**Human runbook:** [walkthrough-signoff-sigma-clinical.md](walkthrough-signoff-sigma-clinical.md)

| Step | You do |
|------|--------|
| 1 Orient | TUI or `npm run dev`; focus sigma + clinical_suite; confirm workflows in JSON |
| 2 Spawn | tmux + `terminal-session register` or dashboard spawn; bound task ids |
| 3 Govern | `project-intake --show`; `init` slices if ready (or log Gaps) |
| 4 Complete | `observe-session complete` or `liaison-session-done` → check `.spark-flow/tasks/<id>/` |
| 5 Validate | `liaison validate --profile sigma` / `python` |
| Sign-off | Fill table + Gaps in walkthrough doc |
| Done | Mark **B.5 Done** in [track-b-portfolio.md](finish-backlog/track-b-portfolio.md) |

**Note:** Preflight may show `ready_to_build: false` — that is OK; document blockers under **Gaps / tickets**.
