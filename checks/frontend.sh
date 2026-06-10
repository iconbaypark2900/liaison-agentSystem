#!/usr/bin/env bash
# Frontend validation profile.
# Graceful: emits not_applicable (exit 0) when this repo is not a frontend project.
set -euo pipefail

if [ ! -f "package.json" ]; then
  echo "not_applicable: no package.json found"
  exit 0
fi

status=0
echo "ok: package.json present"

if [ ! -d "node_modules" ]; then
  echo "warn: node_modules absent; run npm install before validating build/tests"
  exit 0
fi

has_script() {
  node -e "process.exit(((require('./package.json').scripts||{})['$1'])?0:1)" 2>/dev/null
}

if has_script lint; then
  echo "running: npm run lint"
  npm run lint --silent || status=$?
fi

if has_script test; then
  echo "running: npm test"
  npm test --silent || status=$?
else
  echo "warn: no test script defined in package.json"
fi

if has_script build; then
  echo "running: npm run build"
  npm run build --silent || status=$?
fi

exit "$status"
