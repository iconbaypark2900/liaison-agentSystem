# PROJECT_SPEC.md

## Project

spark-flow-demo

## Goal

Build a small Python CLI package that checks whether the local DGX Spark coding-agent environment is healthy.

## CLI command

```bash
spark-demo-health
```

## Required output

The CLI should print a readable health report with:

- Python version
- platform system/release/machine
- current working directory
- whether `ollama` exists on PATH
- whether `http://127.0.0.1:11434/api/tags` responds
- installed Ollama model names
- whether these expected models are installed:
  - `qwen3.6:latest`
  - `qwen3-coder:30b`
  - `gpt-oss:20b`
  - `nemotron-3-nano:30b-a3b-q4_K_M`

## Exit behavior

- Exit code `0` when the CLI runs successfully and Ollama is reachable.
- Exit code `1` when Python works but Ollama is not reachable.
- Exit code `2` only for unexpected internal errors.

## Constraints

- Use only the Python standard library.
- Do not use `psutil`.
- Do not add runtime dependencies.
- Use `argparse`.
- Use `urllib.request` for the Ollama API check.
- Use `shutil.which` to check for binaries.
- Keep functions small, typed, and testable.
- Handle malformed Ollama JSON gracefully.

## Expected files after implementation

```text
pyproject.toml
README.md
PROJECT_SPEC.md
TASKS.md
DECISIONS.md
AGENTS.md
CLAUDE.md
src/spark_flow_demo/__init__.py
src/spark_flow_demo/cli.py
tests/test_cli.py
```
