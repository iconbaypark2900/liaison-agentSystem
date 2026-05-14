#!/usr/bin/env bash
set -euo pipefail

test -f quantum/quantum_config.yaml
test -f quantum/backend_registry.yaml
test -f quantum/benchmark_plan.yaml
test -f quantum/results_schema.json
test -f quantum/experiment_log.jsonl

if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

python -m pytest tests/quantum
