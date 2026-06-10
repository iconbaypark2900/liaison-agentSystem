#!/usr/bin/env bash
# Wave-1 Tier A portfolio bootstrap — project-intake --show only (dry).
# Keys from registry/project_plans.yaml. Track B.1 — see docs/finish-backlog/track-b-portfolio.md
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIAISON="${ROOT}/bin/liaison"

TIER_A_KEYS=(
  sigma
  clinical_suite
  adaptive_graph_rag
  research
  materialScience
)

echo "== portfolio bootstrap wave 1 (intake --show) =="
for key in "${TIER_A_KEYS[@]}"; do
  echo ""
  echo "--- ${key} ---"
  "${LIAISON}" project-intake --project "$key" --show || {
    echo "warn: project-intake failed for ${key} (repo may be missing on disk)" >&2
  }
done
echo ""
echo "done: wave 1 intake show complete"
