# Dashboard web — production deploy

The command center UI lives in `dashboard/web` (Next.js App Router). Hosting is an operator choice; this doc is the **ADR** for Spark/DGX and same-host production.

**Related:** [execution-bridge.md](execution-bridge.md) · [finish-backlog/track-d-production.md](finish-backlog/track-d-production.md) · [dashboard/README.md](../dashboard/README.md)

---

## Decision (ADR)

**Recommended for Spark/DGX:** **D.2a same-host** — run `dashboard/web` on the workstation or DGX where `bin/liaison`, tmux, `memory/`, and venture queue already live. Terminal spawn (`POST /api/terminal/spawn`), venture queue APIs, and allowlisted `liaison` writes require co-location with the liaison CLI.

**Alternative (read-only remote):** **D.2b Vercel** — managed Next.js with preview URLs. Suitable when the dashboard only ingests exported JSON (`memory/snapshots/latest.json` or periodic snapshot ingest). **Constraints:** no reliable tmux/wezterm spawn from Vercel functions; `LIAISON_ROOT` on serverless must point at a reachable path or you run snapshot-only mode; `memory/terminal_sessions.json` and live `command-center --json` need a sync path or read-only snapshot API.

**Deferred unless requested:** **D.2c Fly.io** — single-region app + volume for `memory/`; only choose if you need a remote VM with liaison CLI on the same machine. Not the default Spark path.

**Parking lot:** **D.4 Dashboard auth** — basic auth or SSO in front of the dashboard; document break-glass when implemented. See [track-d-production.md](finish-backlog/track-d-production.md).

---

## Capability vs hosting option

| Capability | D.2a same-host | D.2b Vercel (read-only) | D.2c Fly (co-located) |
|------------|----------------|-------------------------|------------------------|
| `POST /api/terminal/spawn` (tmux/wezterm) | Yes — `TERMINAL_BRIDGE=tmux` | No — cloud has no operator tmux | Yes if liaison + tmux on same VM |
| `memory/venture_queue.json` read/write | Yes — local disk | No — unless synced/object store | Yes — Fly volume |
| `memory/terminal_sessions.json` | Yes | No — unless synced | Yes with volume |
| Live `liaison command-center --json` | Yes — `LIAISON_ROOT` local | Snapshot ingest or remote path only | Yes if CLI on VM |
| Allowlisted `POST /api/liaison/run` | Yes | Risky / path-dependent | Yes if CLI on VM |
| JSON refresh (`?refresh=1`) | Full refresh via local CLI | Limited to snapshot or slow remote shell | Full if CLI co-located |

---

## Local / dev (default)

```bash
cd dashboard/web
npm ci
npm run dev
```

Set `LIAISON_ROOT` to the liaison_agentSystem checkout. API routes shell out to `bin/liaison` and read JSON from `dashboard/command_center`.

Copy env template:

```bash
cp dashboard/web/.env.local.example dashboard/web/.env.local
```

---

## D.2a — Same-host production (recommended)

### One-shot start

From repo root (after env is configured):

```bash
cp dashboard/web/.env.production.example dashboard/web/.env.production
# Edit LIAISON_ROOT if the checkout path differs

chmod +x scripts/run-dashboard-prod.sh
./scripts/run-dashboard-prod.sh
```

The script checks `LIAISON_ROOT` (defaults to repo root), runs `npm ci`, `npm run build`, and `npm run start` on port **3000**.

### Required env (production)

| Variable | Purpose |
|----------|---------|
| `LIAISON_ROOT` | Absolute path to liaison_agentSystem |
| `LIAISON_ENV` | e.g. `PROD` (gate strip) |
| `TERMINAL_BRIDGE` | `tmux` (recommended on DGX) or `wezterm` / `copy` |

Template: `dashboard/web/.env.production.example`.

Optional: `LIAISON_WORKLOAD_ID` — L5 flywheel workload chip when `PROJECT_PHASE.md` is not on disk.

### Reverse proxy (optional)

Example nginx snippet: [`deploy/nginx-liaison-dashboard.conf.example`](../deploy/nginx-liaison-dashboard.conf.example) — proxy `http://127.0.0.1:3000`.

### Health check

`GET /api/health` returns `{ "ok": true }` (no liaison shell-out). Use for load balancers and post-deploy smoke:

```bash
curl -sf http://127.0.0.1:3000/api/health
```

Command-center data still requires `LIAISON_ROOT` and a working `liaison command-center --json` for `/api/command-center`.

---

## D.2b — Vercel (alternative, not default)

- Link `dashboard/web` as the Vercel project root.
- Set env vars in Vercel; prefer **read-only** dashboard fed by `scripts/snapshot-command-center.sh` → `memory/snapshots/latest.json` if the build host cannot see DGX paths.
- Do **not** expect terminal spawn or venture queue mutation from serverless unless you operate a private bridge (out of scope here).

---

## D.2c — Fly.io (deferred)

Deploy `dashboard/web` as a Fly Machine with a volume for `memory/` only when an operator explicitly wants a remote co-located VM. Same constraints as D.2a for spawn: liaison CLI must be on that machine.

---

## CI (D.3 / D.5)

GitHub Actions workflow: [`.github/workflows/liaison-command-center.yml`](../.github/workflows/liaison-command-center.yml)

On `pull_request` and `push` to `main`:

- Python: `tests/test_command_center_data.py`, `bash tests/test_command_center_json.sh`
- Web: `cd dashboard/web && npm ci && npm test -- --run`

No deploy secrets required for this workflow.

Local parity:

```bash
python3 tests/test_command_center_data.py
bash tests/test_command_center_json.sh
cd dashboard/web && npm ci && npm test -- --run
```

---

## Out of scope (documented only)

- Vercel production deploy automation (D.2b) — operator choice per ADR above
- Auth / SSO in front of the dashboard (D.4)
- Wiring Fly volumes to per-repo `.spark-flow/memory` (D.2c)

See [execution-bridge.md](execution-bridge.md) for terminal spawn and venture queue behavior that must stay co-located with tmux.
