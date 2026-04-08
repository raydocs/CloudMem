#!/usr/bin/env bash
set -euo pipefail

# Zero-config setup:
#   cd cloudflare
#   ./setup.sh            # secure mode (default)
#   ./setup.sh --quick    # no bearer/hmac auth (local demo only)

MODE="secure"
if [[ "${1:-}" == "--quick" ]]; then
  MODE="quick"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v npx >/dev/null 2>&1; then
  echo "[ERR] npx not found. Install Node.js first." >&2
  exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "[ERR] openssl not found. Please install OpenSSL." >&2
  exit 1
fi

echo "[setup] Wrangler login"
npx wrangler whoami >/dev/null 2>&1 || npx wrangler login

THREAD_API_TOKEN=""
THREAD_HMAC_SECRET=""

if [[ "$MODE" == "secure" ]]; then
  THREAD_API_TOKEN="$(openssl rand -hex 24)"
  THREAD_HMAC_SECRET="$(openssl rand -hex 32)"
  echo "[setup] Generated secure token + hmac"
else
  echo "[setup] Quick mode: auth disabled"
fi

echo "[setup] Deploying Cloudflare resources"
THREAD_API_TOKEN="$THREAD_API_TOKEN" THREAD_HMAC_SECRET="$THREAD_HMAC_SECRET" ./deploy.sh

WORKER_URL=""
if [[ -f .deploy.meta ]]; then
  # shellcheck disable=SC1091
  source ./.deploy.meta
  WORKER_URL="${WORKER_URL:-}"
fi

CLOUDMEM_HOME="${CLOUDMEM_HOME:-$HOME/.cloudmem}"
mkdir -p "$CLOUDMEM_HOME"
ENV_FILE="$CLOUDMEM_HOME/thread_remote.env"

{
  echo "# CloudMem thread remote config"
  if [[ -n "$WORKER_URL" ]]; then
    echo "export CLOUDMEM_THREAD_REMOTE_URL=\"$WORKER_URL/v1/thread/finalize\""
  else
    echo "# Worker URL was not auto-detected. Set this manually:"
    echo "# export CLOUDMEM_THREAD_REMOTE_URL=\"https://<your-worker-url>/v1/thread/finalize\""
    echo "unset CLOUDMEM_THREAD_REMOTE_URL"
  fi

  if [[ "$MODE" == "secure" ]]; then
    echo "export CLOUDMEM_THREAD_REMOTE_TOKEN=\"$THREAD_API_TOKEN\""
    echo "export CLOUDMEM_THREAD_REMOTE_HMAC_SECRET=\"$THREAD_HMAC_SECRET\""
  else
    echo "# quick mode (no auth)"
    echo "unset CLOUDMEM_THREAD_REMOTE_TOKEN"
    echo "unset CLOUDMEM_THREAD_REMOTE_HMAC_SECRET"
  fi
} > "$ENV_FILE"

echo
echo "✅ Setup complete"
echo "Env file written: $ENV_FILE"
echo "Run this once per shell:"
echo "  source $ENV_FILE"

if [[ -z "$WORKER_URL" ]]; then
  echo
  echo "⚠️  Worker URL not detected automatically."
  echo "Open Cloudflare Dashboard -> Workers & Pages -> cloudmem-thread-ledger"
  echo "Copy the public URL and set CLOUDMEM_THREAD_REMOTE_URL manually."
fi

echo
echo "Then test:"
echo "  cloudmem thread list --limit 5"
