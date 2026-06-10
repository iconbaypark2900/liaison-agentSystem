# Track D — Production & hosting (P3b deploy + R6)

**Purpose:** Pick one hosting model, deploy the dashboard, add CI smoke, and optional auth. Full terminal-bridge finish almost always means **D.2a** on the DGX, not D.2b alone.

[Index ←](README.md) · **Deploy ADR:** [dashboard-web-deploy.md](../dashboard-web-deploy.md)

**Pick one hosting model first** (D.1 ADR before D.2*).

---

| ID | Title | Size | Status | Deps | Done when |
|----|--------|------|--------|------|-----------|
| **D.1** | Hosting decision record | S | **Done** | — | ADR in [dashboard-web-deploy.md](../dashboard-web-deploy.md) (Decision + capability table) |
| **D.2a** | Same-host production | M | **Done** | D.1 | `scripts/run-dashboard-prod.sh`; `.env.production.example`; optional nginx example; `/api/health` documented |
| **D.2b** | Vercel read-only dashboard | L | Deferred | D.1, A.3 | Documented in ADR; not implemented |
| **D.2c** | Fly co-located app | L | Deferred | D.1 | Operator-request only; noted in ADR |
| **D.3** | CI deploy workflow | M | **Done** | D.2* | `.github/workflows/liaison-command-center.yml` — pytest-style + JSON smoke + vitest |
| **D.4** | Dashboard auth (optional) | L | Parking lot | D.2* | Basic auth or SSO; document break-glass |
| **D.5** | R6 E2E in CI | S | **Done** | D.3 | `test_command_center_json.sh` + vitest on PR (same workflow) |

---

## Operator quick start (D.2a)

```bash
cp dashboard/web/.env.production.example dashboard/web/.env.production
./scripts/run-dashboard-prod.sh
curl -sf http://127.0.0.1:3000/api/health
```

Optional reverse proxy: `deploy/nginx-liaison-dashboard.conf.example`.
