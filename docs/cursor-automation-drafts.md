# Cursor automation drafts (A.4, A.5)

Ready-to-paste specs for **Cursor Automations** in the product UI. These cannot be created from repo code; configure in Cursor → Automations.

Parent: [finish-backlog/track-a-training-wheels.md](finish-backlog/track-a-training-wheels.md) · Setup: [operator-training-wheels.md](operator-training-wheels.md)

**Prerequisite:** [scripts/snapshot-command-center.sh](../scripts/snapshot-command-center.sh) (or cron) writes `memory/snapshots/latest.json`.

**Prefill YAML:**

- A.4: [automation-prefills/liaison-weekday-digest.yaml](automation-prefills/liaison-weekday-digest.yaml)
- A.5: [automation-prefills/liaison-tier-a-pr-gate-comment.yaml](automation-prefills/liaison-tier-a-pr-gate-comment.yaml)

**Setup guide:** [cursor-automations-setup.md](cursor-automations-setup.md)

---

## 1. Weekday digest (A.4)

| Field | Value |
|-------|--------|
| **Name** | Liaison weekday digest |
| **Trigger** | Cron — weekdays 08:00 local (adjust timezone) |
| **Repo / context** | Liaison checkout with `memory/snapshots/latest.json` (DGX path or synced copy) |

### Prompt body (paste into automation)

```text
You are the Liaison operator digest assistant. Read the file memory/snapshots/latest.json from this workspace (refresh it first with ./scripts/snapshot-command-center.sh if older than 1 hour).

Produce a short Slack/email-style digest with these sections:

1. **Stale executor sessions** — from JSON:
   - List `.stale_executor_sessions[]` (agent, project, task_id, hours_stale if present).
   - Also flag `.terminal_sessions[]` where status is running and started_at is older than `.workstation_profile.executor_session_stale_hours` (default 4).

2. **Venture queue depth** — from JSON:
   - `.venture_queue_summary.pending_count`, `.running_count`, `.total_items`, `.max_active_ventures`.

3. **Projects not ready to build** — Tier A keys from registry/project_plans.yaml:
   - For each of: sigma, clinical_suite, adaptive_graph_rag, research, materialScience
   - Run mentally from focused JSON: `bin/liaison command-center --json --project <key>` and report any where `.project_intake.ready_to_build` is false OR `.summary.ready_to_build` is false when that project is selected.
   - If you only have the unfocused snapshot, note that `.summary.ready_to_build` applies to the focused project only; still list Tier A keys and recommend `liaison project-intake --project <key> --show` for any with open kanban intake tasks under `.kanban.todo[]` / `.kanban.doing[]` matching that repo path prefix in `.registered_projects.<key>.path`.

4. **Hub health** — one line: `.hub_status`, `.summary.open_tasks`, `.summary.blockers`.

Use jq for extraction when helpful. Example jq paths on the default snapshot:
- `.generated_at`
- `.venture_queue_summary.pending_count`
- `.stale_executor_sessions`
- `.terminal_sessions`
- `.summary.ready_to_build` (focused-project only in single snapshot)
- `.registered_projects | keys` with `.registered_projects.<key>.default_profile == "none"` for Tier C count

Keep the digest under 40 lines. End with: "Next: fix top intake blocker or run liaison observe-session complete for stale sessions."
```

### jq reference (command-center JSON shape)

| Metric | jq path |
|--------|---------|
| Snapshot time | `.generated_at` |
| Queue pending | `.venture_queue_summary.pending_count` |
| Queue running | `.venture_queue_summary.running_count` |
| Stale sessions (precomputed) | `.stale_executor_sessions` |
| Live terminal sessions | `.terminal_sessions` |
| Global open tasks | `.summary.open_tasks` |
| Intake blockers (focused) | `.summary.intake_blockers` |
| Ready to build (focused) | `.summary.ready_to_build` |
| Per-project intake (focused fetch) | `.project_intake.ready_to_build`, `.project_intake.blockers[].liaison_cmd` |

---

## 2. Tier A PR engineering-gate comment (A.5)

| Field | Value |
|-------|--------|
| **Name** | Liaison Tier A PR gate commands |
| **Trigger** | Pull request opened (GitHub) |
| **Repo filter** | Match registry keys that have entries in `registry/project_plans.yaml`: `sigma`, `clinical_suite`, `adaptive_graph_rag`, `research`, `materialScience` (map to actual GitHub repo names / paths on your org) |

### Prompt body (paste into automation)

```text
On pull request open, read registry/project_plans.yaml in the Liaison workspace. Match the PR repository to a project_plans key (sigma, clinical_suite, adaptive_graph_rag, research, materialScience).

Post a single PR comment (copy-only, do not run commands) titled "Liaison engineering gate (copy-paste)" containing:

- project key and intent from YAML
- engineering_gate_summary
- engineering_gate_commands as a fenced bash block (from project_plans.<key>.engineering_gate_commands)
- research_gate_commands as a second fenced block if the PR is draft or labeled "research"

If no matching project_plans key, do not comment.

Reminder footer: "Executor path requires liaison observe-session complete after pane work; hooks do not replace governance."
```

### Example comment template (sigma)

```markdown
## Liaison engineering gate (copy-paste)

**Project:** `sigma` — Trading platform; incremental tradeFluxsimulator archive migration into Sigma

**Engineering gate:** Hermes-led slices with sigma validation profile; governed-slice when audit trail required.

```bash
liaison validate --profile sigma
liaison start-pattern hermes-led-slice --task-id sigma-slice-1
liaison start-pattern governed-slice --task-id sigma-governed-1
```

**Research gate (if applicable):**

```bash
liaison assess-project --show
liaison project-intake --project sigma --show
liaison init sigma-tfs-1 "Archive inspect slice" --workflow sigma-integration
```
```

---

## Status

| ID | Repo deliverable | UI status |
|----|------------------|-----------|
| A.4 | This doc §1 | **Draft (UI)** — create automation in Cursor |
| A.5 | This doc §2 | **Draft (UI)** — create automation in Cursor |
