# START HERE — Liaison v0.2.0 Full Assembly Bundle

This bundle is the corrected full-picture assembly package for Liaison v0.2.0.

## What changed from the earlier bundle

The previous ZIP had complete portfolio/config/code assets but the major `docs/v0.2.0/*.md` files were short summaries. This bundle replaces them with full implementation specifications covering:

- version freeze
- architecture
- dual workstation profiles
- runtime config
- model routing/budgets
- executor adapters
- worker run-once/task queue
- evidence/validation/gates
- confidence calibration
- local-agents integration
- project portfolio assignment
- portfolio task generation
- portfolio CLI integration
- Codex implementation plan

## Safe install

Unzip outside the repo first:

```bash
mkdir -p /tmp/liaison_v020_full
unzip liaison_v020_full_assembly_bundle.zip -d /tmp/liaison_v020_full
```

Then inspect:

```bash
cd /tmp/liaison_v020_full
find . -maxdepth 3 -type f | sort | sed -n '1,200p'
```

Copy into repo with ignore-existing first:

```bash
cd /path/to/liaisonAgentSystem
rsync -av --ignore-existing /tmp/liaison_v020_full/ ./
```

Review before overwriting existing CLI files:

```text
src/liaison/cli.py
src/liaison/__main__.py
src/liaison/__init__.py
bin/liaison
pyproject.toml
```

## First safe commands

```bash
python -m pytest tests/test_portfolio_cli.py -q
python -m pytest tests/test_portfolio_task_generation.py -q
python -m liaison portfolio validate --json
python -m liaison portfolio generate-tasks --dry-run --limit 6
```

## First branch

```bash
git checkout -b agent/liaison/v0.2.0-alpha1-portfolio-cli
```

## What not to do first

Do not run worker tasks yet. Do not call models. Do not call executors. Do not deploy. Do not trade. Do not push main.
