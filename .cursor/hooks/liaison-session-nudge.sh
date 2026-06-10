#!/usr/bin/env bash
# Training wheels: nudge operator to complete venture-bound executor sessions.
# See docs/operator-training-wheels.md
set -euo pipefail

MODE="${1:-}"
INPUT="$(cat)"

find_operator_session() {
  local mem="${PWD}/.spark-flow/memory/operator_session.json"
  if [[ -f "$mem" ]]; then
    echo "$mem"
    return 0
  fi
  return 1
}

read_session_fields() {
  local mem="$1"
  python3 - <<'PY' "$mem"
import json, sys
path = sys.argv[1]
try:
    data = json.load(open(path))
except Exception:
    sys.exit(1)
pk = (data.get("project_key") or "").strip()
tid = (data.get("task_id") or "").strip()
if pk and tid:
    print(f"{pk}\t{tid}")
PY
}

session_end_nudge() {
  local mem fields project task
  mem="$(find_operator_session)" || return 0
  fields="$(read_session_fields "$mem" 2>/dev/null || true)"
  [[ -n "$fields" ]] || return 0
  project="${fields%%$'\t'*}"
  task="${fields#*$'\t'}"

  msg="Venture session bound (project=${project}, task=${task}). When the executor pane exits, run: bin/liaison-session-done <agent> <exit-code> [log-file]"
  if command -v jq >/dev/null 2>&1; then
    echo "$(jq -n --arg m "$msg" '{followup_message: $m, user_message: $m}')"
  else
    printf '%s\n' "$msg"
  fi
}

after_shell_nudge() {
  local command=""
  if command -v jq >/dev/null 2>&1; then
    command="$(echo "$INPUT" | jq -r '.command // empty')"
  else
    command="$(echo "$INPUT" | grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/' || true)"
  fi
  [[ -n "$command" ]] || return 0

  if ! echo "$command" | grep -qE '(^|[[:space:]/])hermes([[:space:]]|$)|(^|[[:space:]/])qca([[:space:]]|$)|(^|[[:space:]/])ml_intern([[:space:]]|$)'; then
    return 0
  fi

  local mem fields project task hint
  mem="$(find_operator_session 2>/dev/null || true)"
  if [[ -n "$mem" ]]; then
    fields="$(read_session_fields "$mem" 2>/dev/null || true)"
    if [[ -n "$fields" ]]; then
      project="${fields%%$'\t'*}"
      task="${fields#*$'\t'}"
      hint="liaison observe-session complete --agent <agent> --exit-code \$? --project ${project} --task-id ${task}"
    fi
  fi
  hint="${hint:-liaison observe-session complete --agent <agent> --exit-code \$? --project <key> --task-id <id>}"

  local msg="Executor command finished. Record outcome in pane B: ${hint}  (or bin/liaison-session-done)"
  if command -v jq >/dev/null 2>&1; then
    echo "$(jq -n --arg m "$msg" --arg a "$msg" '{user_message: $m, agent_message: $a}')"
  else
    printf '%s\n' "$msg"
  fi
}

case "$MODE" in
  session-end) session_end_nudge ;;
  after-shell) after_shell_nudge ;;
  *) exit 0 ;;
esac

exit 0
