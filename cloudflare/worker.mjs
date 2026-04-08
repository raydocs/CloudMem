export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return withCors(new Response(null, { status: 204 }), env);
    }

    if (request.method === "POST" && url.pathname === "/v1/thread/finalize") {
      return handleFinalize(request, env);
    }

    if (request.method === "GET" && url.pathname === "/v1/threads") {
      return handleList(url, env);
    }

    if (request.method === "GET" && url.pathname.startsWith("/v1/thread/")) {
      const pathParts = url.pathname.split("/");
      const threadId = pathParts[3];
      
      // Check if requesting transcript
      if (pathParts.length === 5 && pathParts[4] === "transcript") {
        return handleTranscript(threadId, env);
      }
      
      return handleShow(threadId, env);
    }

    return json({ error: "not_found" }, 404, env);
  },
};

function withCors(response, env) {
  const headers = new Headers(response.headers);
  headers.set("Access-Control-Allow-Origin", env.CORS_ORIGIN || "*");
  headers.set("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  headers.set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Timestamp, X-Signature");
  headers.set("Vary", "Origin");
  return new Response(response.body, { status: response.status, headers });
}

function json(payload, status = 200, env) {
  return withCors(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "content-type": "application/json; charset=utf-8" },
    }),
    env
  );
}

async function readJson(request) {
  try {
    return await request.json();
  } catch {
    return null;
  }
}

function timingSafeEqual(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  let out = 0;
  for (let i = 0; i < a.length; i++) out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return out === 0;
}

async function verifyAuth(request, env, rawBody) {
  const requiredToken = env.THREAD_API_TOKEN || "";
  if (requiredToken) {
    const auth = request.headers.get("authorization") || "";
    if (!auth.startsWith("Bearer ")) return { ok: false, reason: "missing_bearer" };
    const token = auth.slice("Bearer ".length).trim();
    if (!timingSafeEqual(token, requiredToken)) return { ok: false, reason: "invalid_bearer" };
  }

  const secret = env.THREAD_HMAC_SECRET || "";
  if (!secret) return { ok: true };

  const ts = request.headers.get("x-timestamp") || "";
  const sig = request.headers.get("x-signature") || "";
  if (!ts || !sig) return { ok: false, reason: "missing_signature" };

  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const msg = encoder.encode(`${ts}.${rawBody}`);
  const digest = await crypto.subtle.sign("HMAC", key, msg);
  const hex = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
  const expected = `sha256=${hex}`;
  if (!timingSafeEqual(expected, sig)) return { ok: false, reason: "bad_signature" };

  return { ok: true };
}

async function handleFinalize(request, env) {
  const raw = await request.text();
  const auth = await verifyAuth(request, env, raw);
  if (!auth.ok) return json({ error: auth.reason }, 401, env);

  let payload;
  try {
    payload = JSON.parse(raw);
  } catch {
    return json({ error: "invalid_json" }, 400, env);
  }

  const threadId = String(payload.thread_id || payload.session_id || "").trim();
  if (!threadId) return json({ error: "missing_thread_id" }, 400, env);

  const endedAt = String(payload.ended_at || payload.saved_at || new Date().toISOString());
  const date = endedAt.slice(0, 10);
  const key = `threads/${date}/${threadId}.json`;

  // 1) Raw source of truth in R2 (optional)
  if (env.THREADS_R2) {
    await env.THREADS_R2.put(key, JSON.stringify(payload));
    
    // Store transcript if provided
    if (payload.transcript_content) {
      const transcriptKey = `transcripts/${threadId}.jsonl`;
      await env.THREADS_R2.put(transcriptKey, payload.transcript_content);
      // Remove transcript content from payload to avoid storing twice
      delete payload.transcript_content;
    }
  }

  // 2) Query index in D1
  await env.THREADS_DB.prepare(
    `INSERT INTO thread_ledger (
      thread_id, session_id, repo, branch, mode, status, created_at, ended_at, duration_sec,
      prompt_count, token_input, token_output, context_used_pct, cost_usd, cost_is_estimated,
      lines_added, lines_deleted, lines_modified, files_changed, oracle_used, tool_calls_count,
      transcript_path, commit_sha, sync_status, ingest_status, error_code, error_detail,
      remote_status, remote_detail, updated_at
    ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9,
              ?10, ?11, ?12, ?13, ?14, ?15,
              ?16, ?17, ?18, ?19, ?20, ?21,
              ?22, ?23, ?24, ?25, ?26, ?27,
              ?28, ?29, ?30)
    ON CONFLICT(thread_id) DO UPDATE SET
      session_id=excluded.session_id,
      repo=excluded.repo,
      branch=excluded.branch,
      mode=excluded.mode,
      status=excluded.status,
      created_at=excluded.created_at,
      ended_at=excluded.ended_at,
      duration_sec=excluded.duration_sec,
      prompt_count=excluded.prompt_count,
      token_input=excluded.token_input,
      token_output=excluded.token_output,
      context_used_pct=excluded.context_used_pct,
      cost_usd=excluded.cost_usd,
      cost_is_estimated=excluded.cost_is_estimated,
      lines_added=excluded.lines_added,
      lines_deleted=excluded.lines_deleted,
      lines_modified=excluded.lines_modified,
      files_changed=excluded.files_changed,
      oracle_used=excluded.oracle_used,
      tool_calls_count=excluded.tool_calls_count,
      transcript_path=excluded.transcript_path,
      commit_sha=excluded.commit_sha,
      sync_status=excluded.sync_status,
      ingest_status=excluded.ingest_status,
      error_code=excluded.error_code,
      error_detail=excluded.error_detail,
      remote_status=excluded.remote_status,
      remote_detail=excluded.remote_detail,
      updated_at=excluded.updated_at`
  )
    .bind(
      threadId,
      payload.session_id || "",
      payload.repo || "",
      payload.branch || "",
      payload.mode || "",
      payload.status || "",
      payload.created_at || "",
      payload.ended_at || "",
      payload.duration_sec || 0,
      payload.prompt_count || 0,
      payload.token_input || 0,
      payload.token_output || 0,
      payload.context_used_pct || 0,
      payload.cost_usd || 0,
      payload.cost_is_estimated ? 1 : 0,
      payload.lines_added || 0,
      payload.lines_deleted || 0,
      payload.lines_modified || 0,
      payload.files_changed || 0,
      payload.oracle_used ? 1 : 0,
      payload.tool_calls_count || 0,
      payload.transcript_path || "",
      payload.commit_sha || "",
      payload.sync_status || "",
      payload.ingest_status || "",
      payload.error_code || "",
      payload.error_detail || "",
      payload.remote_status || "uploaded",
      payload.remote_detail || "",
      new Date().toISOString()
    )
    .run();

  return json({ ok: true, thread_id: threadId, r2_key: key }, 200, env);
}

async function handleList(url, env) {
  const limit = Math.max(1, Math.min(200, Number(url.searchParams.get("limit") || 20)));
  const rows = await env.THREADS_DB.prepare(
    `SELECT thread_id, session_id, repo, branch, mode, status, ended_at, duration_sec,
            prompt_count, token_input, token_output, context_used_pct, cost_usd,
            lines_added, lines_deleted, lines_modified, oracle_used
       FROM thread_ledger
      ORDER BY ended_at DESC
      LIMIT ?1`
  )
    .bind(limit)
    .all();
  return json({ threads: rows.results || [], count: (rows.results || []).length }, 200, env);
}

async function handleShow(threadId, env) {
  if (!threadId) return json({ error: "missing_thread_id" }, 400, env);
  const row = await env.THREADS_DB.prepare(`SELECT * FROM thread_ledger WHERE thread_id = ?1`).bind(threadId).first();
  if (!row) return json({ error: "thread_not_found" }, 404, env);
  return json({ thread: row }, 200, env);
}

async function handleTranscript(threadId, env) {
  if (!threadId) return json({ error: "missing_thread_id" }, 400, env);
  
  // First get the thread to find the R2 key
  const row = await env.THREADS_DB.prepare(`SELECT * FROM thread_ledger WHERE thread_id = ?1`).bind(threadId).first();
  if (!row) return json({ error: "thread_not_found" }, 404, env);
  
  // Try to get transcript from R2
  if (env.THREADS_R2) {
    // Try multiple possible key formats
    const possibleKeys = [
      `transcripts/${threadId}.jsonl`,
      `transcripts/${threadId}.json`,
      `threads/${row.ended_at?.slice(0, 10) || 'unknown'}/${threadId}.jsonl`,
      `threads/${row.ended_at?.slice(0, 10) || 'unknown'}/${threadId}.json`,
    ];
    
    for (const key of possibleKeys) {
      try {
        const object = await env.THREADS_R2.get(key);
        if (object) {
          const content = await object.text();
          return new Response(content, {
            status: 200,
            headers: {
              "Content-Type": "text/plain; charset=utf-8",
              "Access-Control-Allow-Origin": env.CORS_ORIGIN || "*",
              "Cache-Control": "public, max-age=3600"
            }
          });
        }
      } catch (e) {
        // Continue to next key
      }
    }
  }
  
  return json({ error: "transcript_not_found" }, 404, env);
}
