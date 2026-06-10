#!/usr/bin/env bash
# Run key Python tests without requiring pytest (stdlib unittest-style scripts).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== liaison python smoke =="
python3 tests/test_venture_queue.py
python3 tests/test_execution_bridge.py
python3 tests/test_project_intake.py
python3 tests/test_command_center_data.py
python3 tests/test_learning_bridge.py

echo "ok"
