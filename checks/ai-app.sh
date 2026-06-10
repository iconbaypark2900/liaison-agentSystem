#!/usr/bin/env bash
# AI-app validation profile (LLM/agent apps: Node or Python).
# Graceful: emits not_applicable (exit 0) when no recognized app manifest is found.
set -euo pipefail

if [ ! -f "package.json" ] && [ ! -f "pyproject.toml" ]; then
  echo "not_applicable: no package.json or pyproject.toml found"
  exit 0
fi

status=0

# Secret hygiene: AI apps commonly leak provider keys.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if git ls-files | grep -E '(^|/)\.env($|\.)' >/dev/null 2>&1; then
    echo "FAIL: tracked .env file detected (move provider keys out of git)"
    status=1
  else
    echo "ok: no tracked .env files"
  fi
fi

if [ -f ".env.example" ] || [ -f ".env.sample" ]; then
  echo "ok: env example present"
else
  echo "warn: add .env.example documenting required provider keys"
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
fi

exit "$status"
