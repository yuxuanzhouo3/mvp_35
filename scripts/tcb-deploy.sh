#!/usr/bin/env bash
# Deploy CloudRun with MinNum=0 for both api and web (scale-to-zero when idle).
# Platform idle reclaim is about 10 minutes with no traffic; next request cold-starts.
# Usage:
#   scripts/tcb-deploy.sh api
#   scripts/tcb-deploy.sh web
set -euo pipefail

export PATH="/Users/mac-guest1/.nvm/versions/node/v20.19.5/bin:/bin:/usr/bin:/usr/sbin:/sbin:${PATH:-}"
ENV_ID="${TCB_ENV_ID:-mvp35-d6g2zp4539a542ebc}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-}"

if [[ "$TARGET" != "api" && "$TARGET" != "web" ]]; then
  echo "usage: $0 api|web" >&2
  exit 2
fi

if [[ "$TARGET" == "api" ]]; then
  NAME=pickglobal-api
  MIN_NUM=0
  SRC="$ROOT/backend"
  STAGE="$(mktemp -d /tmp/pickglobal-api-XXXX)"
  trap 'rm -f "$STAGE/cloudbase-auth.json"; rm -rf "$STAGE"' EXIT
  rsync -a \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude 'data' \
    --exclude 'cloudbase-auth.json' \
    "$SRC/" "$STAGE/"
  cp -f "$HOME/.config/.cloudbase/auth.json" "$STAGE/cloudbase-auth.json"
  chmod 600 "$STAGE/cloudbase-auth.json"
else
  NAME=pickglobal-web
  MIN_NUM=0
  SRC="$ROOT/front"
  STAGE="$(mktemp -d /tmp/pickglobal-web-XXXX)"
  trap 'rm -rf "$STAGE"' EXIT
  rsync -a \
    --exclude 'node_modules' \
    --exclude '.next' \
    --exclude '.turbo' \
    "$SRC/" "$STAGE/"
fi

cd "$STAGE"
tcb -y cloudrun deploy \
  -e "$ENV_ID" \
  -s "$NAME" \
  --force \
  --wait \
  --min-num "$MIN_NUM" \
  --max-num 2 \
  --open-access-types PUBLIC
echo "DEPLOYED $NAME min-num=$MIN_NUM max-num=2"
