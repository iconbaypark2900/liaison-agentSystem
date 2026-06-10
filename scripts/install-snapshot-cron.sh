#!/usr/bin/env bash
# Install a user crontab entry for liaison command-center snapshots (Track A.3 → A.4).
# Usage: ./scripts/install-snapshot-cron.sh [--every-minutes 15] [--dry-run]

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SNAPSHOT="${ROOT}/scripts/snapshot-command-center.sh"
EVERY=15
DRY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --every-minutes) EVERY="${2:?}"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -h|--help)
      echo "Usage: $0 [--every-minutes 15] [--dry-run]"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

[[ -x "$SNAPSHOT" ]] || chmod +x "$SNAPSHOT"
LINE="*/${EVERY} * * * * ${SNAPSHOT} >> ${ROOT}/memory/snapshots/cron.log 2>&1"
MARKER="# liaison-agentSystem snapshot (A.3)"

if [[ "$DRY" -eq 1 ]]; then
  echo "Would append to crontab:"
  echo "$MARKER"
  echo "$LINE"
  exit 0
fi

mkdir -p "${ROOT}/memory/snapshots"
TMP="$(mktemp)"
crontab -l 2>/dev/null | grep -v "$MARKER" | grep -v "snapshot-command-center.sh" >"$TMP" || true
{
  echo "$MARKER"
  echo "$LINE"
} >>"$TMP"
crontab "$TMP"
rm -f "$TMP"
echo "Installed crontab entry (every ${EVERY} min):"
crontab -l | grep -A1 "$MARKER" || true
echo "Log: ${ROOT}/memory/snapshots/cron.log"
