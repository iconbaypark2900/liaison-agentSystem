# Cursor Automations setup (A.4 + A.5)

Step-by-step for operators. Repo cannot create automations for you; use **Cursor → Automations** in the desktop app (Agents window recommended for editor handoff).

Prefills: [automation-prefills/](automation-prefills/)

---

## Prerequisites

1. **A.3 snapshot on DGX** (before weekday digest is useful):

   ```bash
   ./scripts/install-snapshot-cron.sh --every-minutes 15
   # or manual: ./scripts/snapshot-command-center.sh
   ```

2. Liaison workspace opened in Cursor: `liaison_agentSystem` checkout with `LIAISON_ROOT` / `bin/liaison` working.

---

## A.4 — Weekday digest

| Step | Action |
|------|--------|
| 1 | Open **Automations** → **New automation** |
| 2 | Name: `Liaison weekday digest` |
| 3 | Trigger: **Cron** — weekdays 08:00 (your timezone) |
| 4 | Tools: none required (read files in workspace) |
| 5 | Prompt: copy from [liaison-weekday-digest.yaml](automation-prefills/liaison-weekday-digest.yaml) `workflow.prompts[0].prompt` or [cursor-automation-drafts.md](cursor-automation-drafts.md) §1 |
| 6 | Save; run once manually to verify it reads `memory/snapshots/latest.json` |

**Done when:** Monday test run produces stale sessions + queue + Tier A intake notes.

---

## A.5 — Tier A PR gate comment

| Step | Action |
|------|--------|
| 1 | **New automation** — `Liaison Tier A PR gate commands` |
| 2 | Trigger: **Git** → Pull request **opened** |
| 3 | Repo scope: map GitHub repos to keys in `registry/project_plans.yaml` (`sigma`, `clinical_suite`, `adaptive_graph_rag`, `research`, `materialScience`) |
| 4 | Tool: **Comment on PR** |
| 5 | Prompt: [liaison-tier-a-pr-gate-comment.yaml](automation-prefills/liaison-tier-a-pr-gate-comment.yaml) or [cursor-automation-drafts.md](cursor-automation-drafts.md) §2 |
| 6 | Fill **gitConfig** repo/branch in UI if the editor requires a checkout |

**Done when:** Opening a test PR on a Tier A repo posts the engineering gate bash block (copy-only).

---

## Mark track A complete

Update [finish-backlog/track-a-training-wheels.md](finish-backlog/track-a-training-wheels.md): set **A.4** and **A.5** to **Done** after both automations run successfully once.
