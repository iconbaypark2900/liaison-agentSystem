#!/usr/bin/env bash
# Backend validation profile.
# Graceful: emits not_applicable (exit 0) when this repo is not a backend project.
set -euo pipefail

has_openapi=""
for candidate in openapi.yaml openapi.yml openapi.json api/openapi.yaml docs/openapi.yaml; do
  if [ -f "$candidate" ]; then
    has_openapi="$candidate"
    break
  fi
done

if [ -z "$has_openapi" ] && [ ! -d "tests" ]; then
  echo "not_applicable: no openapi.* spec and no tests/ directory found"
  exit 0
fi

status=0

if [ -n "$has_openapi" ]; then
  echo "ok: API spec present ($has_openapi)"
else
  echo "warn: no openapi.* spec found (expected for a backend profile)"
fi

if [ -f "pyproject.toml" ] || [ -d ".venv" ]; then
  if [ -d ".venv" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi
  if [ -d "tests" ]; then
    echo "running: pytest"
    python -m pytest || status=$?
  else
    echo "warn: no tests/ directory; skipping pytest"
  fi
elif [ -f "package.json" ]; then
  if [ -d "node_modules" ]; then
    echo "running: npm test"
    npm test --silent || status=$?
  else
    echo "warn: node_modules absent; run npm install before validating tests"
  fi
else
  echo "warn: no recognized backend toolchain (pyproject.toml/.venv or package.json)"
fi

exit "$status"
