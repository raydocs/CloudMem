# CloudMem Thread Ledger + Cloudflare

CloudMem now writes AMP-style thread logs locally and can optionally push each record to a remote endpoint (e.g. Cloudflare Worker).

## Local ledger

Stored under:

- `~/.cloudmem/threads/<thread_id>.json` (latest snapshot per thread)
- `~/.cloudmem/threads/YYYY/MM/DD/index.jsonl` (append-only index)
- `~/.cloudmem/threads/YYYY/MM/DD/events.jsonl` (append-only raw events)

CLI:

```bash
cloudmem thread list --limit 20
cloudmem thread show <thread_id>
```

MCP tools:

- `cloudmem_thread_list`
- `cloudmem_thread_show`

## One-command setup (recommended)

```bash
cd cloudflare
./setup.sh
# then
source ~/.cloudmem/thread_remote.env
```

`setup.sh` will login via Wrangler, deploy Worker + D1 + R2, generate secure token/HMAC by default, and write local CloudMem env vars.

Use quick (no-auth) demo mode only for local testing:

```bash
./setup.sh --quick
```

## Optional Cloudflare upload

Set environment variables where `session-finalize` runs:

```bash
export CLOUDMEM_THREAD_REMOTE_URL="https://<worker-domain>/v1/thread/finalize"
export CLOUDMEM_THREAD_REMOTE_TOKEN="<bearer-token>"   # optional but recommended
export CLOUDMEM_THREAD_REMOTE_HMAC_SECRET="<hmac-secret>"  # optional
```

Upload behavior:

- If `CLOUDMEM_THREAD_REMOTE_URL` is unset, upload is skipped.
- If upload succeeds: `remote_status=uploaded`.
- If upload fails: `remote_status=failed` with `remote_detail`.

## Worker request format

`POST` JSON body is the saved thread payload (same as `thread show` output).
Headers include:

- `Authorization: Bearer <token>` (if configured)
- `X-Timestamp: <unix-seconds>`
- `X-Signature: sha256=<hmac>` (if HMAC secret configured)

HMAC message format:

`<timestamp>.<raw_request_body_bytes>`

Use SHA-256 with your shared secret.

## Cloudflare Pages web view (always online)

A minimal Pages frontend is included in `cloudflare/pages/`.

Deploy:

```bash
cd cloudflare/pages
npx wrangler pages project create cloudmem-threads-web
npx wrangler pages deploy . --project-name cloudmem-threads-web
```

### Use your domain: `littlescene.com`

Recommended mapping:

- Pages UI: `threads.littlescene.com`
- Worker API: `api.littlescene.com`

Set Worker CORS to only allow your UI domain when deploying:

```bash
cd cloudflare
CORS_ORIGIN="https://threads.littlescene.com" ./setup.sh
```

Then in Cloudflare Dashboard:

1. Workers & Pages → `cloudmem-threads-web` (Pages project) → **Custom domains** → add `threads.littlescene.com`.
2. Workers & Pages → `cloudmem-thread-ledger` (Worker) → **Settings → Domains & Routes** → add custom domain `api.littlescene.com`.
3. Wait for certificates to become Active, then open `https://threads.littlescene.com`.

Note: add custom domain from Pages/Workers dashboard first, do not only create DNS record manually (to avoid 522).

The Worker includes CORS headers, so Pages can call `/v1/threads` and `/v1/thread/:id` directly.

## Suggested Cloudflare storage split

- R2 for raw append-only artifacts
- D1 for indexed query/search of thread summaries
- (Optional) Durable Objects for per-thread serialized writes
