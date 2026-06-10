#!/usr/bin/env bash
# Same-host production: build and start the Next.js command center on :3000.
# Requires LIAISON_ROOT (or defaults to this repo). See docs/dashboard-web-deploy.md
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIAISON_ROOT="${LIAISON_ROOT:-$ROOT}"
export LIAISON_ROOT

if [[ ! -f "${LIAISON_ROOT}/bin/liaison" && ! -f "${LIAISON_ROOT}/bin/spark-flow" ]]; then
  echo "error: LIAISON_ROOT must point at liaison_agentSystem (missing bin/liaison): ${LIAISON_ROOT}" >&2
  exit 1
fi

WEB="${ROOT}/dashboard/web"
if [[ ! -f "${WEB}/package.json" ]]; then
  echo "error: dashboard/web not found under ${ROOT}" >&2
  exit 1
fi

cd "$WEB"
if [[ -f .env.production ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.production
  set +a
elif [[ -f .env.production.local ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.production.local
  set +a
fi

export NODE_ENV=production
echo "LIAISON_ROOT=${LIAISON_ROOT}"
echo "== npm ci =="
npm ci
echo "== npm run build =="
npm run build
echo "== npm run start (http://0.0.0.0:3000) =="
exec npm run start
