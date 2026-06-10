# Walkthrough sign-off: sigma + clinical_suite (B.5)

Human runbook for the two-project portfolio walkthrough. Automations and scripts do not replace this sign-off.

Parent: [finish-backlog/track-b-portfolio.md](finish-backlog/track-b-portfolio.md) · Closeout hub: [operator-closeout-checklist.md](operator-closeout-checklist.md) · Smoke: [execution-bridge.md](execution-bridge.md#e2e-operator-smoke-a6)

**Status:** **Ready for human sign-off** (not Done until sections 2–5 checkboxes and sign-off table are completed).

**Automated preflight:** `bash scripts/b5-walkthrough-preflight.sh`

---

## Automated preflight (repo / agent)

Re-run before sign-off:

```bash
bash scripts/b5-walkthrough-preflight.sh
cd dashboard/web && npm test -- --run   # optional
```

| Check | Result |
|-------|--------|
| E2E smoke | Pass |
| Snapshot + wave-1 bootstrap | Pass |
| sigma / clinical_suite on disk | Pass (paths in `registry/repos.yaml`) |
| `project-intake --show` both | Pass (blockers OK — record in Gaps) |
| `command-center --json` both | Pass (`ready_to_build` may be **false** — expected until hygiene) |

Human sections below still require live tmux, `observe-session complete`, and validate on real repos.

---

## Prerequisites

- [x] `bash tests/e2e_operator_smoke.sh` *(preflight script)*
- [x] `bash scripts/bootstrap-portfolio-wave1.sh` *(preflight script)*
- [x] `memory/snapshots/latest.json` fresh *(preflight script)*
- [x] sigma and clinical_suite repos on disk *(preflight script)*

---

## 1. Orient

- [ ] Open command center: `bin/liaison command-center` or dashboard `npm run dev` in `dashboard/web`
- [ ] Focus **sigma** — confirm plan card shows `sigma-integration` workflow and engineering gate commands
- [ ] Focus **clinical_suite** — confirm `reporter-mode` / python validation profile
- [ ] Copy research gate commands from plan or `liaison project-intake --project <key> --show`

```bash
bin/liaison command-center --json --project sigma | jq '.project_plan.workflow, .summary.ready_to_build'
bin/liaison command-center --json --project clinical_suite | jq '.project_plan.workflow, .summary.ready_to_build'
```

---

## 2. Spawn (dry or live)

- [ ] Venture queue empty or acknowledged: `bin/liaison venture-queue list`
- [ ] Register terminal session (dry checklist — optional live tmux):

```bash
bin/liaison terminal-session register \
  --agent-name hermes \
  --launch "cd ~/quantumGlobalGroup/sigma && hermes" \
  --project sigma \
  --task-id sigma-walkthrough-1 \
  --pattern hermes-led-slice
```

- [ ] Repeat pattern for **clinical_suite** with `--project clinical_suite --task-id clinical-walkthrough-1`

---

## 3. Govern

- [ ] Run intake show for both projects; resolve or document blockers

```bash
bin/liaison project-intake --project sigma --show
bin/liaison project-intake --project clinical_suite --show
```

- [ ] Init slice tasks only if `ready_to_build` (or document waiver in gaps section)

```bash
bin/liaison init sigma-walkthrough-1 "Walkthrough archive inspect" --workflow sigma-integration
bin/liaison init clinical-walkthrough-1 "Walkthrough clinical slice" 
```

- [ ] Hooks fire open: `.cursor/hooks.json` session-end nudge after a test session (optional)

---

## 4. Observe-session complete

- [ ] Complete session with dry or real exit code (failure path exercises eval draft):

```bash
bin/liaison observe-session complete \
  --agent hermes --exit-code 0 \
  --project sigma --task-id sigma-walkthrough-1

bin/liaison-session-done hermes 0 /tmp/hermes-walkthrough.log
```

- [ ] Confirm artifacts under repo `.spark-flow/tasks/<task-id>/` (OBSERVATIONS, events.jsonl)

---

## 5. Validate

- [ ] Profile validation (may fail until repos ready — record outcome):

```bash
bin/liaison validate --profile sigma
bin/liaison validate --profile python
```

- [ ] Re-run smoke: `bash tests/e2e_operator_smoke.sh`

---

## Sign-off

| Project | Operator | Date | Pass / Fail | Notes |
|---------|----------|------|-------------|-------|
| sigma | | | | |
| clinical_suite | | | | |

---

## Gaps / tickets

Use this section during sign-off; copy rows into your issue tracker.

| ID | Project | Gap | Severity | Ticket |
|----|---------|-----|----------|--------|
| G-001 | | | P0 / P1 / P2 | |
| G-002 | | | | |
| G-003 | | | | |

**Template row:** `G-___ | sigma | <blocker> | P1 | <url>`

---

## Related

- [workflow-yaml-audit.md](workflow-yaml-audit.md) — sigma-integration stub status
- [tier-c-playbook.md](tier-c-playbook.md) — Tier C repos out of walkthrough scope
- [operator-training-wheels.md](operator-training-wheels.md) — hooks + snapshot
