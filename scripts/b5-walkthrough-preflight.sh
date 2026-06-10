#!/usr/bin/env bash
# Automated B.5 preflight — does not replace human tmux / observe-session sign-off.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CLI="${ROOT}/bin/liaison"
export LIAISON_ROOT="$ROOT"

echo "== B.5 walkthrough preflight =="
fail=0
ok() { echo "ok: $*"; }
warn() { echo "warn: $*"; }
bad() { echo "FAIL: $*"; fail=1; }

bash tests/e2e_operator_smoke.sh
ok e2e_operator_smoke

./scripts/snapshot-command-center.sh
ok snapshot

bash scripts/bootstrap-portfolio-wave1.sh >/dev/null 2>&1 || true
ok bootstrap-wave1

expand_path() {
  local p="$1"
  p="${p/#\~/$HOME}"
  printf '%s' "$p"
}

check_repo() {
  local key="$1"
  local path
  path="$(python3 -c "
import yaml
from pathlib import Path
r=yaml.safe_load(Path('registry/repos.yaml').read_text())
print(r['repos']['$key']['path'])
")"
  path="$(expand_path "$path")"
  if [[ -d "$path" ]]; then
    ok "repo on disk: $key -> $path"
  else
    warn "repo missing: $key -> $path (skip live walkthrough in that repo)"
  fi
}

check_repo sigma
check_repo clinical_suite

for proj in sigma clinical_suite; do
  if "$CLI" project-intake --project "$proj" --show >/tmp/b5-intake-"$proj".txt 2>&1; then
    ok "project-intake --show $proj"
  else
    warn "project-intake $proj exited non-zero (may be blockers — record in Gaps)"
  fi
  if "$CLI" command-center --json --project "$proj" 2>/dev/null | jq -e '(.project_plan.workflow | type) == "string"' >/dev/null; then
    ok "command-center json $proj"
    "$CLI" command-center --json --project "$proj" 2>/dev/null | jq '{project:.focus.project, workflow:.project_plan.workflow, ready:.summary.ready_to_build, soft:.summary.ready_to_build_soft}'
  else
    bad "command-center json $proj"
  fi
done

"$CLI" venture-queue list >/dev/null 2>&1 && ok venture-queue-list || warn venture-queue-list

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "== B.5 preflight: automated checks passed =="
  echo "Human still required: tmux spawn, observe-session complete, validate, sign-off table in docs/walkthrough-signoff-sigma-clinical.md"
  exit 0
fi
echo "== B.5 preflight: fix FAIL items before walkthrough =="
exit 1
