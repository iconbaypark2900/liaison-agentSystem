# Operator training wheels

Low-risk nudges that complement [execution-bridge.md](execution-bridge.md). They **do not** replace `liaison observe-session complete` or `bin/liaison-session-done`.

Parent backlog: [finish-backlog/track-a-training-wheels.md](finish-backlog/track-a-training-wheels.md) (Track A).

---

## Cursor project hooks (A.1, A.2)

Files:

- `.cursor/hooks.json`
- `.cursor/hooks/liaison-session-nudge.sh`

### Session end (A.1)

On `stop` and `sessionEnd`, the hook looks for `.spark-flow/memory/operator_session.json` in the current working directory. When `project_key` and `task_id` are set, it reminds you to run:

```bash
bin/liaison-session-done <agent> <exit-code> [log-file]
```

### After executor shell (A.2)

On `afterShellExecution`, when the command matches `hermes`, `qca`, or `ml_intern`, the hook injects a reminder to run `liaison observe-session complete` with the bound project/task.

Hooks fail open (non-blocking). Verify in Cursor **Settings → Hooks** or the Hooks output channel.

---

## Local command-center snapshot (A.3)

Install cron on the DGX (recommended before A.4):

```bash
./scripts/install-snapshot-cron.sh --every-minutes 15
# preview only: ./scripts/install-snapshot-cron.sh --dry-run
```

Manual equivalent:

```bash
*/15 * * * * /path/to/liaison_agentSystem/scripts/snapshot-command-center.sh
```

Writes `memory/snapshots/latest.json` (gitignored). Used by future A.4 weekday digest automations and optional read-only dashboard ingest (Track D.2b).

Manual run:

```bash
./scripts/snapshot-command-center.sh
```

---

## E2E operator smoke (A.6)

Dry-run checklist without live tmux:

```bash
bash tests/e2e_operator_smoke.sh
```

See [execution-bridge.md](execution-bridge.md#e2e-operator-smoke-a6).

---

## Remaining automations (A.4, A.5 — Cursor UI)

**Status: Draft (UI)** — specs are ready to paste; automations are not Done until configured in Cursor.

**Setup:** [cursor-automations-setup.md](cursor-automations-setup.md) · Prefills: [automation-prefills/](automation-prefills/) · [cursor-automation-drafts.md](cursor-automation-drafts.md)

| ID | What to build |
|----|----------------|
| **A.4** | Weekday cron automation — [liaison-weekday-digest.yaml](automation-prefills/liaison-weekday-digest.yaml) |
| **A.5** | PR comment automation — [liaison-tier-a-pr-gate-comment.yaml](automation-prefills/liaison-tier-a-pr-gate-comment.yaml) |
