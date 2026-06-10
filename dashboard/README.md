# Dashboard

Operator model (three surfaces, hub groups, choreography): [../docs/integrated-operator-model.md](../docs/integrated-operator-model.md). Quick reference: [../docs/operator-quick-reference.md](../docs/operator-quick-reference.md).

This directory has two related surfaces:

1. **Generated artifacts** (markdown/JSON from CLI) — ignored by git except this README.
2. **Web command center** — [`web/`](web/) Next.js app (TypeScript, local dev).

## Generated artifacts (CLI)

Regenerate with:

```bash
liaison look --refresh
liaison index-tasks --show
liaison discover-projects --show
liaison plan-next --show
liaison dashboard --show
```

`liaison look` prints a cross-repo summary; the commands above write files under `dashboard/` (e.g. `DASHBOARD.md`, `tasks.json`).

## Web command center (Next.js)

Terminal UI remains `liaison command-center` (Textual). The browser dashboard reads the same state via JSON:

```bash
# Verify JSON export
liaison command-center --json --refresh | head

# Web app
cp dashboard/web/.env.local.example dashboard/web/.env.local
# Edit LIAISON_ROOT if needed

cd dashboard/web
npm install
npm run dev
# http://localhost:3000
```

Routes: `/` (3-column L8 layout), `/projects`, `/hub`, `/ops`, `/settings`.

**Production (same-host):** [docs/dashboard-web-deploy.md](../docs/dashboard-web-deploy.md) — ADR recommends DGX co-location; `./scripts/run-dashboard-prod.sh` after `cp dashboard/web/.env.production.example dashboard/web/.env.production`.

API: `GET /api/command-center?refresh=1&project=<repo_key>&task=<task_id>&pattern=<pattern_id>` spawns `liaison command-center --json`.

Allowlisted writes (browser only): `POST /api/liaison/run` with `{ "cmd": "liaison start-pattern …", "project": "<optional>" }`.
Never runs agent launch lines (hermes, qca, etc.) — use terminal copy/Open in terminal on `/hub`.

## Operator workflow (browser + terminal)

Two surfaces by design:

1. **Browser** — project focus, hub operator deck, pattern scaffold, reporter checklist, copy helpers.
2. **Terminal** — run `hermes`, `qca`, `ml-intern`, etc. and watch live output.

On `/hub`:

- **Copy launch** / **Open in terminal** — agent execution stays in the terminal pane.
- **Copy attach** — `liaison attach <agent> --title "Report" --text "<paste agent output>"`
- **Copy reporter bundle** — cd hint, init, attach, validate in one block.
- **Scaffold pattern** — allowlisted `liaison start-pattern` via API (refreshes dashboard state).

On `/` and `/ops` (when a project is selected): **Reporter checklist** shows open tasks (click to bind `?task=`), disk-backed step status (✓/○/!), and Init → Close copy commands. **Sync liaison** on the gate strip hard-refreshes JSON after terminal governance.

URL session: `?project=`, `?task=`, `?pattern=` stay in sync with `CommandCenterContext`. Optional CLI persistence: `liaison command-center --json --project X --task Y --persist-session` writes `<repo>/.spark-flow/memory/operator_session.json`.

Terminal session registry: `memory/terminal_sessions.json` (repo-local). After tmux/wezterm spawn, `POST /api/terminal/spawn` registers via `liaison terminal-session register`. List/prune: `liaison terminal-session list|prune`.

**Project intake** (before Hermes): select a project on `/` to see the **Intake** panel and gate-strip pills. Scoring runs in `collect_command_center_state` (and standalone via `liaison project-intake --project <key> --json`). Executor **Open in terminal** is disabled until `summary.ready_to_build` is true; fix commands are copied from blocker rows.

Settings documents `TERMINAL_BRIDGE=copy|tmux|wezterm`. When tmux/wezterm is available, `POST /api/terminal/spawn` opens a window with the launch line; otherwise clipboard fallback.
