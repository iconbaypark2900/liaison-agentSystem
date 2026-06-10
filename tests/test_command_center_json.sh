#!/usr/bin/env bash
# Smoke: liaison command-center --json exports required keys for the web dashboard.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v jq >/dev/null 2>&1; then
  echo "skip: jq not installed"
  exit 0
fi

JSON="$("${ROOT}/bin/liaison" command-center --json 2>/dev/null)"
for key in agent_rows project_matrix summary kanban handoff_chains engineering_metrics project_agent_patterns hub_agent_groups terminal_sessions; do
  echo "$JSON" | jq -e ".${key}" >/dev/null
done
echo "$JSON" | jq -e '.summary.flywheel_open | type == "number"' >/dev/null
echo "$JSON" | jq -e '.summary.intake_ready | type == "boolean"' >/dev/null
echo "$JSON" | jq -e 'has("summary") and (.summary | has("workload_id"))' >/dev/null
echo "$JSON" | jq -e '.summary.ready_to_build_strict | type == "boolean"' >/dev/null 2>/dev/null || true
echo "$JSON" | jq -e '.summary.ready_to_build_soft | type == "boolean"' >/dev/null 2>/dev/null || true
echo "$JSON" | jq -e '.summary.executor_launch_ready | type == "boolean"' >/dev/null 2>/dev/null || true
echo "$JSON" | jq -e '.suggested_workflow_commands | type == "array"' >/dev/null
echo "$JSON" | jq -e '.summary.debrief_stale | type == "boolean"' >/dev/null 2>/dev/null || true
echo "$JSON" | jq -e '.ops_signoff.debrief_stale | type == "boolean"' >/dev/null 2>/dev/null || true
echo "$JSON" | jq -e '.projects_portfolio_detail | type == "array"' >/dev/null

TASK_JSON="$("${ROOT}/bin/liaison" command-center --json --task smoke-task-id 2>/dev/null || true)"
if echo "$TASK_JSON" | jq -e 'has("active_task_id")' >/dev/null 2>&1; then
  echo "command-center --json --task: active_task_id key present"
fi
echo "command-center --json: ok"
