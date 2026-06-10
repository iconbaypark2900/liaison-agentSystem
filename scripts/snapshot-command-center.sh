#!/usr/bin/env bash
# Write command-center JSON snapshot for digest automations and read-only dashboard ingest.
# Track A.3 — see docs/operator-training-wheels.md
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT}/memory/snapshots"
OUT_FILE="${OUT_DIR}/latest.json"

mkdir -p "$OUT_DIR"
"${ROOT}/bin/liaison" command-center --json > "${OUT_FILE}.tmp"
mv "${OUT_FILE}.tmp" "$OUT_FILE"
echo "snapshot: ${OUT_FILE}"
