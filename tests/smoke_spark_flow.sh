#!/usr/bin/env bash
# Smoke test: Liaison parser plus reporter-first task filesystem commands.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

"${ROOT}/bin/liaison" --help >/dev/null
"${ROOT}/bin/spark-flow" --help >/dev/null
python3 -m py_compile "${ROOT}/bin/spark-flow"

cd "$TMPDIR"
git init -q
git config user.email smoke@example.com
git config user.name "Smoke Test"
echo '# Smoke Repo' > README.md
printf 'test:\n\t@echo smoke test\n' > Makefile
git add README.md
git commit -q -m init

"${ROOT}/bin/liaison" init smoke-001 "Exercise reporter mode"
for file in BRIEF.md CONTEXT.md APPROVALS.md DECISIONS.md HANDOFFS.md VALIDATION.md CLOSEOUT.md OBJECTIVES.md OBSERVATIONS.md EVALUATIONS.md LEARNINGS.md IMPROVEMENTS.md FEEDBACK_LOOP.md; do
  test -f ".spark-flow/tasks/smoke-001/$file"
done

"${ROOT}/bin/spark-flow" snapshot --show >/dev/null
"${ROOT}/bin/spark-flow" attach hermes --title "Smoke report" --text "Reporter mode works."
ARTIFACT="$(find .spark-flow/tasks/smoke-001/outbox -type f -name '*smoke-report.md' | head -n 1)"
test -n "$ARTIFACT"
"${ROOT}/bin/spark-flow" approve-artifact "$ARTIFACT" --note "Smoke approval"
test -f ".spark-flow/tasks/smoke-001/approved/$(basename "$ARTIFACT")"
"${ROOT}/bin/spark-flow" reject-artifact "$ARTIFACT" "Smoke rejection path"
test -f ".spark-flow/tasks/smoke-001/rejected/$(basename "$ARTIFACT")"
"${ROOT}/bin/spark-flow" decision "Use reporter mode for smoke test"
"${ROOT}/bin/spark-flow" objective "Keep smoke test aligned" --metric "All feedback artifacts are created"
"${ROOT}/bin/spark-flow" observe hermes --title "Smoke observation" --text "The reporter flow produced an artifact."
"${ROOT}/bin/spark-flow" evaluate "Smoke flow satisfies objective" --rubric alignment --score 5
"${ROOT}/bin/spark-flow" learn "Reporter artifacts make handoff state explicit."
"${ROOT}/bin/spark-flow" improve "Keep smoke coverage for the feedback loop." --priority high --owner agent-system
"${ROOT}/bin/spark-flow" feedback-cycle --show >/dev/null
"${ROOT}/bin/spark-flow" score-artifacts --show --fail-under 3 >/dev/null
test -f ".spark-flow/tasks/smoke-001/SCORES.md"
test -f ".spark-flow/tasks/smoke-001/scores.json"
"${ROOT}/bin/spark-flow" drift-check --show >/dev/null
"${ROOT}/bin/spark-flow" gate --show >/dev/null
"${ROOT}/bin/spark-flow" promote-learning --tags "smoke,feedback" >/dev/null
"${ROOT}/bin/spark-flow" memory-report --limit 5 >/dev/null
"${ROOT}/bin/spark-flow" trend-report --show --limit 10 >/dev/null
test -f "${ROOT}/memory/TREND_REPORT.md"
test -f "${ROOT}/memory/trends.json"
"${ROOT}/bin/spark-flow" index-tasks --show --repo "$TMPDIR" >/dev/null
test -f "${ROOT}/dashboard/TASK_INDEX.md"
test -f "${ROOT}/dashboard/tasks.json"
"${ROOT}/bin/spark-flow" discover-projects --show --repo "$TMPDIR" >/dev/null
test -f "${ROOT}/dashboard/PROJECTS.md"
test -f "${ROOT}/dashboard/projects.json"
"${ROOT}/bin/spark-flow" plan-next --show --repo "$TMPDIR" --limit 5 >/dev/null
test -f "${ROOT}/dashboard/NEXT_WORK.md"
test -f "${ROOT}/dashboard/next_work.json"
"${ROOT}/bin/spark-flow" memory-init --show >/dev/null
test -f ".spark-flow/memory/project_brief.md"
test -f ".spark-flow/memory/current_state.md"
test -f ".spark-flow/memory/decisions.md"
test -f ".spark-flow/memory/tasks/backlog.yaml"
test -f ".spark-flow/memory/memory.sqlite"
"${ROOT}/bin/spark-flow" debrief --show --limit 6 >/dev/null
test -f ".spark-flow/memory/current_state.md"
grep -q "Next recommended action" ".spark-flow/memory/current_state.md"
grep -q "Project phase" ".spark-flow/memory/current_state.md"
DEBRIEF_FILE="$(ls -t .spark-flow/memory/debriefs/*.md | head -n 1)"
grep -q "Recommended choices" "$DEBRIEF_FILE"
grep -q "Stabilize the deterministic baseline" ".spark-flow/memory/tasks/backlog.yaml"
test -f ".spark-flow/memory/project_phase.json"
test -f ".spark-flow/memory/PROJECT_PHASE.md"
"${ROOT}/bin/spark-flow" recommend --show --limit 6 >/dev/null
"${ROOT}/bin/liaison" look --refresh >/dev/null
"${ROOT}/bin/liaison" command-center --once --refresh >/dev/null
"${ROOT}/bin/liaison" command-center --json >/dev/null
"${ROOT}/bin/liaison" tui --once >/dev/null
"${ROOT}/bin/spark-flow" registry phase-routing >/dev/null
"${ROOT}/bin/spark-flow" control-panel --refresh >/dev/null
"${ROOT}/bin/spark-flow" control-panel --interactive >/dev/null
"${ROOT}/bin/spark-flow" choose 1 --show >/dev/null
test -f ".spark-flow/memory/CHOICE.md"
grep -q "Execution plan" ".spark-flow/memory/CHOICE.md"
grep -q "Choice:" ".spark-flow/memory/decisions.md"
"${ROOT}/bin/spark-flow" dashboard --show >/dev/null
test -f "${ROOT}/dashboard/DASHBOARD.md"
"${ROOT}/bin/spark-flow" close-task --summary "Smoke task complete"
"${ROOT}/bin/spark-flow" registry agents >/dev/null

grep -q "Smoke approval" .spark-flow/tasks/smoke-001/APPROVALS.md
grep -q "Use reporter mode" .spark-flow/tasks/smoke-001/DECISIONS.md
grep -q "Smoke flow satisfies objective" .spark-flow/tasks/smoke-001/EVALUATIONS.md
grep -q "Reporter artifacts" .spark-flow/tasks/smoke-001/LEARNINGS.md
grep -q "Antifragile review questions" .spark-flow/tasks/smoke-001/FEEDBACK_LOOP.md
grep -q "No obvious objective drift" .spark-flow/tasks/smoke-001/DRIFT_CHECK.md
grep -q "PASS: objective" .spark-flow/tasks/smoke-001/GATE_REPORT.md
test -f "${ROOT}/memory/smoke-001.learning.md"
grep -q "Smoke task complete" .spark-flow/tasks/smoke-001/CLOSEOUT.md
grep -q "Average score" .spark-flow/tasks/smoke-001/SCORES.md
grep -q "make test" "${ROOT}/dashboard/PROJECTS.md"
grep -q "NEXT WORK" "${ROOT}/dashboard/NEXT_WORK.md"
