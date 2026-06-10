#!/usr/bin/env bash
# Full end-to-end run: register a throwaway repo and walk it through
# Prototype -> Alpha -> Beta -> MVP, asserting phase-aware enforcement.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIAISON="${ROOT}/bin/liaison"
REPOS="${ROOT}/registry/repos.yaml"

REPOS_BACKUP="$(mktemp)"
cp "$REPOS" "$REPOS_BACKUP"
TMPDIR="$(mktemp -d)"
TMPDIR2="$(mktemp -d)"
cleanup() {
  cp "$REPOS_BACKUP" "$REPOS"
  rm -f "$REPOS_BACKUP"
  rm -rf "$TMPDIR" "$TMPDIR2"
}
trap cleanup EXIT

cd "$TMPDIR"
git init -q
git config user.email smoke@example.com
git config user.name "Full Run Smoke"
cat > README.md <<'EOF'
# Full Run Repo

Deploy and rollback are documented here for MVP production readiness.
EOF
printf 'test:\n\t@echo ok\n' > Makefile
git add -A
git commit -q -m init

# --- Register: lifecycle=registered, maturity=unassessed (Prototype is NOT assumed). ---
"$LIAISON" register-project "$TMPDIR" --name full_run_smoke --profile backend >/dev/null
test -f .spark-flow/memory/project_phase.json
test -f .spark-flow/memory/PROJECT_PHASE.md
grep -q '"lifecycle_status": "registered"' .spark-flow/memory/project_phase.json
grep -q '"phase": "unassessed"' .spark-flow/memory/project_phase.json
"$LIAISON" project-phase show | grep -qi "unassessed"

# --- Negative: advance before classify must be blocked ---
if "$LIAISON" project-phase advance --yes >/dev/null 2>&1; then
  echo "ERROR: advance succeeded before classification" >&2
  exit 1
fi

# --- Assess and classify (new repo, no tests/CI -> prototype) ---
"$LIAISON" assess-project --show >/dev/null
test -f .spark-flow/memory/ASSESSMENT.md
grep -qi "Recommended phase" .spark-flow/memory/ASSESSMENT.md
"$LIAISON" project-phase classify --from-assessment --yes >/dev/null
"$LIAISON" project-phase show | grep -qi prototype
grep -q '"lifecycle_status": "classified"' .spark-flow/memory/project_phase.json

# A full governed slice: feedback loop + validation so gate passes at Alpha+.
governed_slice() {
  local id="$1"
  "$LIAISON" init "$id" "Governed slice $id" >/dev/null
  "$LIAISON" snapshot --show >/dev/null
  "$LIAISON" objective "Advance $id" --metric "gate passes" >/dev/null
  "$LIAISON" attach hermes --title "Report" --text "Implemented $id." >/dev/null
  local artifact
  artifact="$(find ".spark-flow/tasks/$id/outbox" -name '*.md' | head -n 1)"
  test -n "$artifact"
  "$LIAISON" approve-artifact "$artifact" --note "ok" >/dev/null
  "$LIAISON" observe hermes --text "Observed $id outcome." >/dev/null
  "$LIAISON" evaluate "Slice $id aligned" --score 5 >/dev/null
  "$LIAISON" decision "Proceed with $id" >/dev/null
  "$LIAISON" validate >/dev/null
  "$LIAISON" feedback-cycle --show >/dev/null
  "$LIAISON" debrief --show >/dev/null
}

# --- Prototype slice (no enforcement) ---
governed_slice proto-001
"$LIAISON" close-task --summary "Prototype demo works" >/dev/null
"$LIAISON" project-phase advance --yes | grep -qi alpha

# --- Negative: Alpha close without gate/validation must be blocked ---
"$LIAISON" init alpha-neg "Snapshot only, should not close" >/dev/null
"$LIAISON" snapshot --show >/dev/null
if "$LIAISON" close-task --summary "should be blocked" >/dev/null 2>&1; then
  echo "ERROR: Alpha close-task succeeded without gate/validation" >&2
  exit 1
fi

# --- Alpha slice (enforced: gate + validation + debrief) ---
governed_slice alpha-001
"$LIAISON" close-task --summary "Alpha slice complete" >/dev/null
"$LIAISON" project-phase advance --yes | grep -qi beta

# --- Beta slice (enforced) ---
governed_slice beta-001
"$LIAISON" close-task --summary "Beta slice complete" >/dev/null
"$LIAISON" project-phase advance --yes | grep -qi mvp

# --- MVP slice (enforced + production-readiness gate) ---
governed_slice mvp-001
"$LIAISON" gate --production --show >/dev/null
"$LIAISON" close-task --summary "MVP slice; deploy and rollback documented" >/dev/null

# --- Assertions ---
"$LIAISON" project-phase show | grep -qi mvp
test -f .spark-flow/memory/built_log.md
grep -q "mvp-001" .spark-flow/memory/built_log.md
grep -q "Next recommended action" .spark-flow/memory/current_state.md
grep -q "Project phase" .spark-flow/tasks/mvp-001/CLOSEOUT.md
grep -q "production readiness" .spark-flow/tasks/mvp-001/CLOSEOUT.md || true
"$LIAISON" start-pattern --list | grep -q "chain:"

# --- Focused: an existing repo (tests + CI) classifies directly to Beta ---
cd "$TMPDIR2"
git init -q
git config user.email smoke@example.com
git config user.name "Existing Repo"
echo "# Existing service" > README.md
mkdir -p tests .github/workflows
touch tests/test_core.py
printf 'name: ci\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ci\n' > .github/workflows/ci.yml
git add -A
git commit -q -m init
"$LIAISON" register-project "$TMPDIR2" --name existing_repo_smoke --profile none >/dev/null
"$LIAISON" project-phase show | grep -qi "unassessed"
"$LIAISON" assess-project >/dev/null
grep -qi "Recommended phase: beta" .spark-flow/memory/ASSESSMENT.md
"$LIAISON" project-phase classify --from-assessment --yes >/dev/null
"$LIAISON" project-phase show | grep -qi beta

echo "FULL_RUN_OK: register -> assess -> classify; prototype -> alpha -> beta -> mvp; existing repo -> beta"
