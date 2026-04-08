#!/usr/bin/env bash
set -euo pipefail

# One-command deploy for CloudMem Thread Ledger on Cloudflare
# Usage:
#   cd cloudflare
#   THREAD_API_TOKEN=xxx THREAD_HMAC_SECRET=yyy ./deploy.sh

WORKER_NAME="${WORKER_NAME:-cloudmem-thread-ledger}"
DB_NAME="${DB_NAME:-cloudmem-threads}"
BUCKET_NAME="${BUCKET_NAME:-cloudmem-threads}"
SCHEMA_FILE="${SCHEMA_FILE:-schema.sql}"
WRANGLER_FILE="${WRANGLER_FILE:-wrangler.toml}"
DEPLOY_META_FILE="${DEPLOY_META_FILE:-.deploy.meta}"

if ! command -v npx >/dev/null 2>&1; then
  echo "[ERR] npx not found. Install Node.js first." >&2
  exit 1
fi

if [[ ! -f "$SCHEMA_FILE" ]]; then
  echo "[ERR] schema file not found: $SCHEMA_FILE" >&2
  exit 1
fi

echo "[1/8] Ensure Wrangler auth"
npx wrangler whoami >/dev/null 2>&1 || npx wrangler login

echo "[2/8] Create D1 database (or resolve existing)"
set +e
D1_OUT=$(npx wrangler d1 create "$DB_NAME" 2>&1)
D1_RC=$?
set -e

DB_ID=""
if [[ $D1_RC -eq 0 ]]; then
  DB_ID=$(echo "$D1_OUT" | sed -n 's/.*database_id = "\([^"]*\)".*/\1/p' | head -n1)
fi

if [[ -z "$DB_ID" ]]; then
  LIST_JSON=$(npx wrangler d1 list --json 2>/dev/null || echo "[]")
  DB_ID=$(python3 - <<'PY' "$LIST_JSON" "$DB_NAME"
import json,sys
raw=sys.argv[1]
name=sys.argv[2]
try:
    rows=json.loads(raw)
except Exception:
    rows=[]
for r in rows:
    if r.get("name")==name:
        print(r.get("uuid") or r.get("id") or "")
        break
PY
)
fi

if [[ -z "$DB_ID" ]]; then
  echo "[ERR] Unable to resolve D1 database id for '$DB_NAME'" >&2
  echo "--- wrangler output ---" >&2
  echo "$D1_OUT" >&2
  exit 1
fi

echo "[3/8] Try to enable R2 bucket (auto-fallback to D1-only)"
R2_ENABLED=1
set +e
R2_OUT=$(npx wrangler r2 bucket create "$BUCKET_NAME" 2>&1)
R2_RC=$?
set -e
if [[ $R2_RC -ne 0 ]]; then
  if echo "$R2_OUT" | grep -Eqi "enable R2|code:\s*10042|code:\s*10136"; then
    echo "  - R2 not enabled on this account, continuing with D1-only mode"
    R2_ENABLED=0
  else
    echo "  - R2 create failed for another reason; continuing with existing bucket assumption"
  fi
fi

echo "[4/8] Write $WRANGLER_FILE"
cat > "$WRANGLER_FILE" <<EOF
name = "$WORKER_NAME"
main = "worker.mjs"
compatibility_date = "2026-04-07"

[[d1_databases]]
binding = "THREADS_DB"
database_name = "$DB_NAME"
database_id = "$DB_ID"
EOF

if [[ "$R2_ENABLED" == "1" ]]; then
  cat >> "$WRANGLER_FILE" <<EOF

[[r2_buckets]]
binding = "THREADS_R2"
bucket_name = "$BUCKET_NAME"
EOF
fi

if [[ -n "${CORS_ORIGIN:-}" ]]; then
  cat >> "$WRANGLER_FILE" <<EOF

[vars]
CORS_ORIGIN = "$CORS_ORIGIN"
EOF
fi

if [[ -n "${WORKER_CUSTOM_DOMAIN:-}" ]]; then
  cat >> "$WRANGLER_FILE" <<EOF

[[routes]]
pattern = "$WORKER_CUSTOM_DOMAIN"
custom_domain = true
EOF
fi

echo "[5/8] Apply D1 schema"
npx wrangler d1 execute "$DB_NAME" --remote --file="./$SCHEMA_FILE"

echo "[6/8] Set Worker secrets (optional but recommended)"
if [[ -n "${THREAD_API_TOKEN:-}" ]]; then
  printf '%s' "$THREAD_API_TOKEN" | npx wrangler secret put THREAD_API_TOKEN >/dev/null
  echo "  - THREAD_API_TOKEN set"
else
  echo "  - THREAD_API_TOKEN not provided (skipped)"
fi

if [[ -n "${THREAD_HMAC_SECRET:-}" ]]; then
  printf '%s' "$THREAD_HMAC_SECRET" | npx wrangler secret put THREAD_HMAC_SECRET >/dev/null
  echo "  - THREAD_HMAC_SECRET set"
else
  echo "  - THREAD_HMAC_SECRET not provided (skipped)"
fi

echo "[7/8] Deploy Worker"
set +e
DEPLOY_OUT=$(npx wrangler deploy 2>&1)
DEPLOY_RC=$?
set -e
if [[ $DEPLOY_RC -ne 0 ]]; then
  echo "$DEPLOY_OUT" >&2
  echo "[ERR] Deploy failed." >&2
  exit 1
fi

echo "$DEPLOY_OUT"
WORKER_URL=$(echo "$DEPLOY_OUT" | grep -Eo 'https://[^ ]+\.workers\.dev' | head -n1 || true)

# Optional sanity check if URL exists
if [[ -n "$WORKER_URL" ]]; then
  set +e
  python3 - <<'PY' "$WORKER_URL" >/dev/null 2>&1
import socket,sys,urllib.parse
host=urllib.parse.urlparse(sys.argv[1]).hostname
socket.gethostbyname(host)
PY
  DNS_RC=$?
  set -e
  if [[ $DNS_RC -ne 0 ]]; then
    echo "[WARN] Deploy returned URL but DNS not resolvable yet: $WORKER_URL"
  fi
fi

echo "[8/8] Write deploy metadata"
cat > "$DEPLOY_META_FILE" <<EOF
WORKER_NAME=$WORKER_NAME
WORKER_URL=$WORKER_URL
D1_DATABASE=$DB_NAME
D1_DATABASE_ID=$DB_ID
R2_ENABLED=$R2_ENABLED
R2_BUCKET=$BUCKET_NAME
EOF

echo
echo "✅ Cloudflare deploy complete"
if [[ -n "$WORKER_URL" ]]; then
  echo "Worker URL: $WORKER_URL"
  echo "Finalize endpoint: $WORKER_URL/v1/thread/finalize"
else
  echo "Worker URL not detected from deploy output."
  echo "Check Cloudflare dashboard -> Workers & Pages -> $WORKER_NAME"
fi
