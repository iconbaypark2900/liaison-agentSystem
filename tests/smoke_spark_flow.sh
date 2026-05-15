#!/usr/bin/env bash
# Smoke test: spark-flow main parser (--help).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"${ROOT}/bin/spark-flow" --help >/dev/null
