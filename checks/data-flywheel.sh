#!/usr/bin/env bash
# Validation check for the data-flywheel antifragile feedback loop.
# Usage:
#   checks/data-flywheel.sh                        # uses .spark-flow/current_task in cwd
#   checks/data-flywheel.sh <repo-path>            # uses current_task in named repo
#   checks/data-flywheel.sh <task-dir-path>        # direct task directory
set -euo pipefail

REPO="${1:-.}"

if [ -f "$REPO/.spark-flow/current_task" ]; then
  TASK_ID=$(cat "$REPO/.spark-flow/current_task")
  TASK_DIR="$REPO/.spark-flow/tasks/$TASK_ID"
elif [ -d "${1:-}" ]; then
  # Caller passed a task directory directly (e.g. for smoke tests)
  TASK_DIR="$1"
elif [ -f ".spark-flow/current_task" ]; then
  TASK_ID=$(cat ".spark-flow/current_task")
  TASK_DIR=".spark-flow/tasks/$TASK_ID"
else
  echo "ERROR: no current task; run 'liaison init <task-id> ...' first" >&2
  exit 1
fi

if [ ! -d "$TASK_DIR" ]; then
  echo "ERROR: task directory not found: $TASK_DIR" >&2
  exit 1
fi

echo "=== data-flywheel loop artifact check ==="
echo "Task dir: $TASK_DIR"

for artifact in OBSERVATIONS.md EVALUATIONS.md LEARNINGS.md IMPROVEMENTS.md; do
  if [ -f "$TASK_DIR/$artifact" ]; then
    echo "  OK: $artifact"
  else
    echo "  MISSING: $artifact — run 'liaison observe/evaluate/learn/improve' before closing"
    exit 1
  fi
done

echo "data-flywheel loop artifacts present"
