# Root tests (control-plane)

Tests in this directory target **committed control-plane assets**: the `spark-flow` CLI, config layout, or other repo-root checks.

They deliberately **do not** replace demos or Python package tests under `examples/` (for example `examples/spark-flow-demo/tests/`), which exercise sample application code instead of the conductor.

## Smoke

From the repository root:

```bash
./tests/smoke_spark_flow.sh
./tests/run_smoke.sh
```

`run_smoke.sh` runs key Python modules via their `if __name__ == "__main__"` entry points (no pytest required).

## Individual tests

Run any module directly:

```bash
python3 tests/test_venture_queue.py
python3 tests/test_execution_bridge.py
python3 tests/test_project_intake.py
python3 tests/test_command_center_data.py
```

With pytest installed (`pip install -r requirements.txt`):

```bash
pytest tests/test_*.py
```

This verifies CLI wiring, venture queue, execution bridge, and command-center data helpers.
