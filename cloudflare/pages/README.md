# CloudMem Pages Frontend

This folder is a minimal Cloudflare Pages frontend for browsing CloudMem threads.

## Deploy

```bash
cd cloudflare/pages
npx wrangler pages project create cloudmem-threads-web
npx wrangler pages deploy . --project-name cloudmem-threads-web
```

Then open the Pages URL and fill in your Worker base URL:

- `https://<worker>.workers.dev`

The frontend calls:

- `GET /v1/threads`
- `GET /v1/thread/:id`

CORS must be enabled on Worker responses (already handled in `cloudflare/worker.mjs`).
