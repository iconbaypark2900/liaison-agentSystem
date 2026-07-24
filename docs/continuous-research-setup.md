# Continuous Edge Discovery — Setup

## Architecture

```
Weekly cron job
      │
      ▼
sigma-research-continuous
      │
  ┌───┴──────────────────────────────────┐
  │    For each sigma account:            │
  │  ┌─────────────────────────────────┐ │
  │  │  StrategyResearchAgent          │ │
  │  │  (Reflexion: hypothesis →       │ │
  │  │   backtest → reflect → repeat)  │ │
  │  └──────────────┬──────────────────┘ │
  │                 │ edge found?         │
  │         ┌───────┴──────────┐         │
  │         │ compare to       │         │
  │         │ champion_tracker │         │
  │         └───────┬──────────┘         │
  │         beats champion by >10%?      │
  │              │ yes                   │
  │    ┌─────────▼──────────┐            │
  │    │  write proposal    │            │
  │    │  update champion   │            │
  │    └────────────────────┘            │
  └──────────────────────────────────────┘
      │
      ▼
memory/champions/<account>.json  ← current best
memory/proposals/<account>.json  ← pending review
```

## Install as weekly cron job

```bash
crontab -e
```

Add this line (runs every Monday at 6 AM):
```cron
0 6 * * 1  cd /home/iconbaypark2900/liaison-agentSystem && python3 bin/sigma-research-continuous >> /tmp/sigma-research.log 2>&1
```

Or run via systemd timer (preferred — handles restarts):

```bash
# /etc/systemd/system/sigma-research.service
[Unit]
Description=Sigma continuous edge research
After=network.target

[Service]
Type=oneshot
User=iconbaypark2900
WorkingDirectory=/home/iconbaypark2900/liaison-agentSystem
ExecStart=/usr/bin/python3 bin/sigma-research-continuous
StandardOutput=append:/var/log/sigma-research.log
StandardError=append:/var/log/sigma-research.log

# /etc/systemd/system/sigma-research.timer
[Unit]
Description=Run sigma edge research weekly

[Timer]
OnCalendar=Mon 06:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sigma-research.timer
sudo systemctl list-timers sigma-research.timer
```

## Usage

```bash
# Seed champion files from prior research results (one-time setup — already done)
sigma-research-continuous --seed-champions

# Run all accounts manually
sigma-research-continuous

# Run one account only
sigma-research-continuous --accounts options_income

# Review pending proposals
sigma-research-continuous --show-proposals

# After you've applied a proposal to sigma config.py, mark it done
sigma-research-continuous --apply-proposal options_income
```

## Improvement threshold

Champions are stored in `memory/champions/`. A challenger must beat the champion
by **>10% on OOS Sharpe** to trigger a proposal. This prevents minor noise from
creating config churn. Edit `IMPROVEMENT_THRESHOLD` in `champion_tracker.py` to
change it.

## What happens when a challenger wins

1. `memory/proposals/<account>.json` is written with full details
2. The champion file is updated to the new winner
3. The console output shows `*** CHAMPION UPDATED ***`

The proposal tells you exactly what to change in `sigma/apps/api/config.py`.
You review it manually before deploying (no auto-deploy by design).

## Bonferroni correction note

After N total hypothesis tests across all accounts and all weekly runs, the
effective false discovery rate rises. Track total tests with:

```bash
grep -r "gate_passed.*true" /home/iconbaypark2900/liaison-agentSystem/memory/research/ | wc -l
```

At 50+ total passing results, apply a Bonferroni correction: raise the
`IMPROVEMENT_THRESHOLD` from 0.10 to 0.15 to stay at ~5% FDR.
```
