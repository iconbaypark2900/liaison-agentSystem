# EXECUTOR_ADAPTER_CONTRACT — Liaison v0.2.0

## Overview

Executor adapters provide a uniform interface for running commands via
subprocess. Each adapter wraps a binary (bash, opencode, codex, claude) and
enforces safety constraints.

## Executor Interface

### `ExecutorStatus`

```python
@dataclass(frozen=True)
class ExecutorStatus:
    executor_id: str
    enabled: bool
    available: bool
    execution_allowed: bool
    command: list[str]
    reason: str
    capabilities: list[str]
```

### `ExecutorResult`

```python
@dataclass(frozen=True)
class ExecutorResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float
    executor_id: str
```

### `run_executor()`

```python
def run_executor(
    executor_id: str,
    args: list[str] | None = None,
    *,
    root: Path = Path("."),
    timeout: int | None = None,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
) -> ExecutorResult
```

**Safety checks before execution:**
1. Executor must be configured in `config/executors.yaml`
2. `enabled` must be `true`
3. Binary must be available in PATH (`shutil.which`)
4. `allow_execution` must be `true` in config

If any check fails, `RuntimeError` is raised with a descriptive message.

**Execution:**
- `subprocess.run()` with `capture_output=True`, `text=True`
- Timeout via `subprocess.TimeoutExpired` → exit_code=-1, stderr includes "TIMEOUT"
- Environment merged with `os.environ.copy()` + caller-provided env
- Working directory from `cwd` parameter

## Configured Executors

| ID | Type | Command | Enabled | allow_execution | Capabilities |
|----|------|---------|---------|-----------------|--------------|
| shell | shell | bash | true | **true** | dry_run, placeholder, validation_commands, diagnostics |
| opencode | opencode | opencode | true | false | dry_run, placeholder, code_generation, refactoring, litellm_route |
| codex | codex | codex | true | false | dry_run, placeholder, code_generation, refactoring, debugging, litellm_route |
| claude_code | claude_code | claude | true | false | dry_run, placeholder, code_review, repo_aware, refactoring |
| ml_intern | external_supervisor | ml-intern | false | false | dry_run, placeholder, research_supervision |

## CLI Interface

### `liaison executor list`

Lists all configured executors with status.

```bash
liaison executor list
liaison executor list --json
```

### `liaison executor ping <id>`

Checks one executor's availability and execution permission.

```bash
liaison executor ping shell
liaison executor ping opencode --json
```

### `liaison executor run <id> [-- <args>...]`

Runs a command via an executor. Only works when `allow_execution: true`.

```bash
liaison executor run shell -- echo hello
liaison executor run shell --timeout 10 -- bash -c "sleep 5; echo done"
liaison executor run shell --cwd /tmp -- ls -la --json
```

**Output (human):**
```
Executor:  shell
Exit code: 0
Duration:  0.012s
--- stdout ---
hello
```

**Output (JSON):**
```json
{
  "exit_code": 0,
  "stdout": "hello\n",
  "stderr": "",
  "duration_sec": 0.012,
  "executor_id": "shell"
}
```

## Enabling an Executor

To enable opencode execution:

1. Install the `opencode` binary in PATH
2. Edit `config/executors.yaml`:
   ```yaml
   opencode:
     enabled: true
     type: opencode
     command: opencode
     allow_execution: true   # ← change from false to true
   ```
3. Verify: `liaison executor ping opencode`

## Worker Integration

The worker calls `run_executor()` through `validate_with_executor()`:

```python
result = run_executor("shell", ["-c", command], cwd=repo_cwd, root=root)
```

This is gated by `policies/validation_execution.yaml`:
- `enabled: false` → placeholder artifacts only
- `enabled: true` + `require_human_approval: true` → needs approval file
- `enabled: true` + `require_human_approval: false` → executes immediately

## Safety Guarantees

1. **No executor runs unless `allow_execution: true`** in config
2. **No executor runs if binary not in PATH**
3. **No executor runs if `enabled: false`**
4. **Worker execution requires policy + approval**
5. **`allow_push` and `allow_main_branch` are always false** in v0.2.0
6. **Timeouts are enforced** via subprocess timeout
7. **No environment leakage** — caller env is merged, not replaced

## Error Handling

| Condition | Behavior |
|-----------|----------|
| Executor not configured | `RuntimeError("Executor 'X' not configured")` |
| Executor disabled | `RuntimeError("Executor 'X' is disabled")` |
| Binary not found | `RuntimeError("Executor 'X' binary not found: ...")` |
| Execution not allowed | `RuntimeError("Executor 'X' execution not allowed by config")` |
| Timeout | `ExecutorResult(exit_code=-1, stderr="...TIMEOUT after Ns")` |
| FileNotFoundError | `RuntimeError("Executor binary not found: ...")` |
