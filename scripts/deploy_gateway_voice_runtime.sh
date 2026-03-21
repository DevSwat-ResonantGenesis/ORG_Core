#!/usr/bin/env bash
set -euo pipefail

# Deploy only gateway voice runtime changes safely from a clean clone.
# Usage:
#   bash scripts/deploy_gateway_voice_runtime.sh
# Optional env overrides:
#   REMOTE_HOST, REMOTE_REPO, REMOTE_BRANCH, REMOTE_TMP_DIR, COMPOSE_FILE, PROJECT_NAME, GATEWAY_SERVICE

REMOTE_HOST="${REMOTE_HOST:-deploy@134.199.221.149}"
REMOTE_REPO="${REMOTE_REPO:-/home/deploy/genesis2026_production_backend}"
REMOTE_BRANCH="${REMOTE_BRANCH:-main}"
REMOTE_TMP_DIR="${REMOTE_TMP_DIR:-/tmp/rg_gateway_voice_runtime}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.unified.yml}"
PROJECT_NAME="${PROJECT_NAME:-genesis2026_production_backend}"
GATEWAY_SERVICE="${GATEWAY_SERVICE:-gateway}"
REMOTE_GIT_URL="${REMOTE_GIT_URL:-}"

ssh "$REMOTE_HOST" \
  REMOTE_REPO="$REMOTE_REPO" \
  REMOTE_BRANCH="$REMOTE_BRANCH" \
  REMOTE_TMP_DIR="$REMOTE_TMP_DIR" \
  COMPOSE_FILE="$COMPOSE_FILE" \
  PROJECT_NAME="$PROJECT_NAME" \
  GATEWAY_SERVICE="$GATEWAY_SERVICE" \
  REMOTE_GIT_URL="$REMOTE_GIT_URL" \
  'bash -s' <<'REMOTE_SCRIPT'
set -euo pipefail

rm -rf "$REMOTE_TMP_DIR"
SOURCE_GIT_URL="$REMOTE_GIT_URL"
if [ -z "$SOURCE_GIT_URL" ]; then
  SOURCE_GIT_URL=$(git -C "$REMOTE_REPO" config --get remote.origin.url || true)
fi

if [ -n "$SOURCE_GIT_URL" ]; then
  git clone --depth 1 --branch "$REMOTE_BRANCH" "$SOURCE_GIT_URL" "$REMOTE_TMP_DIR"
else
  git clone --depth 1 "$REMOTE_REPO" "$REMOTE_TMP_DIR"
  cd "$REMOTE_TMP_DIR"
  if ! git remote get-url origin >/dev/null 2>&1; then
    echo 'ERROR: origin remote is not configured on source repo clone; refusing deploy to avoid stale local overwrite.' >&2
    exit 1
  fi
  git fetch origin "$REMOTE_BRANCH"
  git checkout "$REMOTE_BRANCH"
  git reset --hard "origin/$REMOTE_BRANCH"
fi
cd "$REMOTE_TMP_DIR"

REMOTE_HEAD=$(git ls-remote --heads origin "$REMOTE_BRANCH" | awk '{print $1}')
LOCAL_HEAD=$(git rev-parse HEAD)

if [ -z "$REMOTE_HEAD" ]; then
  echo "ERROR: could not resolve origin/$REMOTE_BRANCH head; refusing deploy." >&2
  exit 1
fi

if [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
  echo "ERROR: local deploy head ($LOCAL_HEAD) does not match origin/$REMOTE_BRANCH ($REMOTE_HEAD); refusing deploy." >&2
  exit 1
fi

echo "Deploying commit $LOCAL_HEAD from origin/$REMOTE_BRANCH"

ENV_ARG=''
if [ -f "$REMOTE_REPO/.env.production" ]; then
  cp "$REMOTE_REPO/.env.production" "$REMOTE_TMP_DIR/.env.production"
  ENV_ARG="--env-file $REMOTE_TMP_DIR/.env.production"
elif [ -f "$REMOTE_REPO/.env" ]; then
  cp "$REMOTE_REPO/.env" "$REMOTE_TMP_DIR/.env"
  ENV_ARG="--env-file $REMOTE_TMP_DIR/.env"
fi

if [ -n "$ENV_ARG" ]; then
  sudo -n docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" $ENV_ARG up -d --build "$GATEWAY_SERVICE"
else
  sudo -n docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d --build "$GATEWAY_SERVICE"
fi

sleep 10

sudo -n docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" ps "$GATEWAY_SERVICE"

curl -fsS http://localhost:8001/health >/tmp/gateway_health.json
cat /tmp/gateway_health.json

sudo -n docker logs --tail 80 "$GATEWAY_SERVICE" | grep -E 'voice/session|uvicorn|startup|error|ERROR' || true

echo 'GATEWAY_VOICE_RUNTIME_DEPLOY_OK'
REMOTE_SCRIPT
