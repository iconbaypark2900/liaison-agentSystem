# Root tests (control-plane)

Tests in this directory target **committed control-plane assets**: the `spark-flow` CLI, config layout, or other repo-root checks.

They deliberately **do not** replace demos or Python package tests under `examples/` (for example `examples/spark-flow-demo/tests/`), which exercise sample application code instead of the conductor.

## Smoke

From the repository root:

```bash
./tests/smoke_spark_flow.sh
```

This verifies `bin/spark-flow --help` exits successfully (CLI wiring and interpreter).
