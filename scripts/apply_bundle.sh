#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR="${1:-}"
TARGET_DIR="${2:-}"

if [[ -z "$BUNDLE_DIR" || -z "$TARGET_DIR" ]]; then
  echo "Usage: scripts/apply_bundle.sh /path/to/unzipped_bundle /path/to/liaisonAgentSystem" >&2
  exit 1
fi

if [[ ! -d "$BUNDLE_DIR" ]]; then
  echo "Bundle directory not found: $BUNDLE_DIR" >&2
  exit 1
fi

if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Target repo directory not found: $TARGET_DIR" >&2
  exit 1
fi

echo "Dry-run copy first:"
rsync -av --dry-run --ignore-existing "$BUNDLE_DIR"/ "$TARGET_DIR"/

echo
read -r -p "Proceed with --ignore-existing copy? [y/N] " ans
if [[ "$ans" != "y" && "$ans" != "Y" ]]; then
  echo "Cancelled."
  exit 0
fi

rsync -av --ignore-existing "$BUNDLE_DIR"/ "$TARGET_DIR"/

echo "Done. Review git status before committing."
