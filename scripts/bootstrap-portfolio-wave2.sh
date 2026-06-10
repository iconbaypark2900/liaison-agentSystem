#!/usr/bin/env bash
# Wave-2 Tier C portfolio bootstrap — project-intake --show for repos not in project_plans.
# Keys: registry/repos.yaml with default_profile: none, excluding registry/project_plans.yaml keys.
# Track B.2 — see docs/finish-backlog/track-b-portfolio.md
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIAISON="${ROOT}/bin/liaison"
REPOS_YAML="${ROOT}/registry/repos.yaml"
PLANS_YAML="${ROOT}/registry/project_plans.yaml"
LOG="${ROOT}/memory/portfolio_bootstrap.log"

mkdir -p "${ROOT}/memory"

# Tier C keys: default_profile none, not listed in project_plans
mapfile -t WAVE2_KEYS < <(
  python3 - <<'PY' "${REPOS_YAML}" "${PLANS_YAML}"
import re
import sys
from pathlib import Path

repos_path, plans_path = Path(sys.argv[1]), Path(sys.argv[2])
plan_keys = set()
for line in plans_path.read_text().splitlines():
    m = re.match(r"^  ([a-zA-Z0-9_]+):\s*$", line)
    if m and m.group(1) != "project_plans":
        plan_keys.add(m.group(1))

repos = {}
current = None
for line in repos_path.read_text().splitlines():
    m = re.match(r"^  ([a-zA-Z0-9_]+):\s*$", line)
    if m:
        current = m.group(1)
        repos[current] = {}
        continue
    if current and "default_profile:" in line:
        repos[current]["profile"] = line.split(":", 1)[1].strip()

for key, meta in sorted(repos.items()):
    if meta.get("profile") != "none":
        continue
    if key in plan_keys:
        continue
    print(key)
PY
)

{
  echo ""
  echo "== $(date -Iseconds) wave 2 bootstrap (intake --show) =="
  echo "keys: ${#WAVE2_KEYS[@]}"
} >>"$LOG"

echo "== portfolio bootstrap wave 2 (Tier C intake --show) =="
echo "logging to ${LOG}"
echo "repos: ${#WAVE2_KEYS[@]}"

for key in "${WAVE2_KEYS[@]}"; do
  echo ""
  echo "--- ${key} ---"
  {
    echo "--- ${key} $(date -Iseconds) ---"
  } >>"$LOG"
  if "${LIAISON}" project-intake --project "$key" --show >>"$LOG" 2>&1; then
    echo "ok: ${key}"
  else
    echo "warn: project-intake failed for ${key} (repo may be missing on disk)" >&2
    echo "warn: intake failed for ${key}" >>"$LOG"
  fi
done

{
  echo "done: wave 2 intake show complete"
} >>"$LOG"
echo ""
echo "done: wave 2 intake show complete (see ${LOG})"
