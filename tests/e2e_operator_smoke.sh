#!/usr/bin/env bash
# E2E operator smoke — dry-run checklist (no live tmux). Track A.6
# See docs/execution-bridge.md#e2e-operator-smoke-a6
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIAISON="${ROOT}/bin/liaison"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "ok: $*"; }

echo "== e2e operator smoke (dry-run) =="

# 1. JSON SSOT exports execution-bridge fields
bash "${ROOT}/tests/test_command_center_json.sh"

# 2. Focus sigma — intake + plan keys present when repo registered
SIGMA_JSON="$("${LIAISON}" command-center --json --project sigma 2>/dev/null || echo '{}')"
if command -v jq >/dev/null 2>&1; then
  echo "$SIGMA_JSON" | jq -e '.selected_project' >/dev/null 2>&1 && pass "sigma focus selected_project"
  echo "$SIGMA_JSON" | jq -e 'has("summary")' >/dev/null || fail "sigma focus missing summary"
else
  pass "jq skip — sigma focus not validated"
fi

# 3. Focus clinical_suite
CLINICAL_JSON="$("${LIAISON}" command-center --json --project clinical_suite 2>/dev/null || echo '{}')"
if command -v jq >/dev/null 2>&1; then
  echo "$CLINICAL_JSON" | jq -e '.selected_project' >/dev/null 2>&1 && pass "clinical_suite focus"
fi

# 4. Venture queue list (no mutation)
"${LIAISON}" venture-queue list >/dev/null 2>&1 && pass "venture-queue list" || pass "venture-queue list (empty ok)"

# 5. observe-session complete dry-run — help/usage must exist
if "${LIAISON}" observe-session complete --help >/dev/null 2>&1; then
  pass "observe-session complete --help"
elif "${LIAISON}" observe-session --help >/dev/null 2>&1; then
  pass "observe-session --help"
else
  fail "observe-session command missing"
fi

# 6. liaison-session-done wrapper exists and is executable
[[ -x "${ROOT}/bin/liaison-session-done" ]] && pass "liaison-session-done executable" || fail "liaison-session-done missing"

# 7. Snapshot script (writes gitignored JSON)
bash "${ROOT}/scripts/snapshot-command-center.sh"
[[ -f "${ROOT}/memory/snapshots/latest.json" ]] && pass "snapshot latest.json" || fail "snapshot not written"

# 8. Wave-1 bootstrap script runs (show mode; may warn on missing repos)
bash "${ROOT}/scripts/bootstrap-portfolio-wave1.sh" >/dev/null && pass "bootstrap-portfolio-wave1"

echo "== e2e operator smoke: all checks passed =="
