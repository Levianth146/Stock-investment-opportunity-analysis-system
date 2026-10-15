#!/usr/bin/env bash
# Build SPA web/ → web/dist
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/web"
if [ -f package-lock.json ]; then npm ci; else npm install; fi
npm run build
echo "OK: web/dist sẵn sàng."
