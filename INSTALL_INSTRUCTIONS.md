# Install Instructions — Liaison v0.2.0 Full Assembly Bundle

## 1. Unzip outside the repo

```bash
mkdir -p /tmp/liaison_v020_full
unzip liaison_v020_full_assembly_bundle.zip -d /tmp/liaison_v020_full
```

## 2. Inspect manifest

```bash
cat /tmp/liaison_v020_full/MANIFEST.md
find /tmp/liaison_v020_full -maxdepth 4 -type f | sort
```

## 3. Copy safely

```bash
cd /path/to/liaisonAgentSystem
rsync -av --ignore-existing /tmp/liaison_v020_full/ ./
```

## 4. If files already exist

Use diffs before overwriting:

```bash
diff -ru src/liaison /tmp/liaison_v020_full/src/liaison || true
diff -ru docs/v0.2.0 /tmp/liaison_v020_full/docs/v0.2.0 || true
```

## 5. Run tests

```bash
python -m pytest tests/test_portfolio_cli.py -q
python -m pytest tests/test_portfolio_task_generation.py -q
```

## 6. Validate portfolio

```bash
python -m liaison portfolio counts --json
python -m liaison portfolio validate --json
python -m liaison portfolio generate-tasks --dry-run --limit 6
```

## 7. Generate first tasks only after dry-run passes

```bash
python -m liaison portfolio generate-tasks --limit 6
```

This only writes task YAML files under `.liaison/tasks/backlog/`.

## 8. Next implementation target

After portfolio CLI works, implement worker `run-once` from `docs/v0.2.0/WORKER_RUNTIME_AND_TASK_QUEUE.md`.
