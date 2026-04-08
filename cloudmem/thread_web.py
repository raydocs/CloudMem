"""Local web UI for CloudMem AMP-style thread views."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from .thread_ledger import list_threads, load_thread, load_thread_events


def _ui_html() -> str:
    return """<!doctype html>
<html>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>CloudMem Threads</title>
  <style>
    body { margin:0; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; background:#f7f7f7; color:#111; }
    .top { height:52px; background:#fff; border-bottom:1px solid #e5e5e5; display:flex; align-items:center; padding:0 16px; font-weight:600; }
    .layout { display:grid; grid-template-columns: 260px 1fr 320px; height: calc(100vh - 52px); }
    .left, .main, .right { overflow:auto; }
    .left { border-right:1px solid #e5e5e5; background:#fff; }
    .main { padding:24px; }
    .right { border-left:1px solid #e5e5e5; background:#fff; padding:16px; }
    .thread-item { padding:12px 14px; border-bottom:1px solid #f0f0f0; cursor:pointer; }
    .thread-item:hover { background:#f8f8f8; }
    .thread-item.active { background:#eef5ff; }
    .muted { color:#666; font-size:12px; }
    h1 { font-size:32px; margin:0 0 8px; }
    .card { background:#fff; border:1px solid #e9e9e9; border-radius:10px; padding:14px; margin-bottom:12px; }
    .ev-title { font-size:13px; color:#444; margin-bottom:8px; }
    .ev-body { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:12px; white-space:pre-wrap; color:#222; }
    .k { font-size:12px; color:#777; margin-top:10px; }
    .v { font-size:14px; margin-top:2px; font-weight:600; }
    .pill { display:inline-block; border:1px solid #ddd; border-radius:999px; padding:3px 9px; font-size:12px; margin:2px 2px 0 0; }
    .cmd { border:1px solid #ddd; background:#fafafa; border-radius:8px; padding:8px; font-family: ui-monospace, monospace; font-size:12px; }
  </style>
</head>
<body>
  <div class='top'>CloudMem Threads</div>
  <div class='layout'>
    <div class='left' id='left'></div>
    <div class='main'>
      <h1 id='title'>Select a thread</h1>
      <div class='muted' id='subtitle'></div>
      <div id='events' style='margin-top:16px'></div>
    </div>
    <div class='right' id='right'><div class='muted'>No thread selected.</div></div>
  </div>

<script>
async function j(url){ const r=await fetch(url); return await r.json(); }
function esc(s){ return String(s ?? '').replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m])); }

function renderRight(t){
  const plus=t.lines_added||0, minus=t.lines_deleted||0, mod=t.lines_modified||0;
  const pct=Number(t.context_used_pct||0).toFixed(1);
  const cost=Number(t.cost_usd||0).toFixed(4);
  const html=`
    <div class='k'>Thread</div><div class='v'>${esc(t.thread_id)}</div>
    <div class='k'>Repo</div><div class='v'>${esc(t.repo||'-')}</div>
    <div class='k'>Branch</div><div class='v'>${esc(t.branch||'-')}</div>
    <div class='k'>Mode</div><div class='v'>${esc(t.mode||'-')}</div>
    <div class='k'>Cost</div><div class='v'>$${cost}${t.cost_is_estimated ? ' (est.)' : ''}</div>
    <div class='k'>Prompts</div><div class='v'>${t.prompt_count||0}</div>
    <div class='k'>Context</div><div class='v'>${pct}%</div>
    <div class='k'>Duration</div><div class='v'>${t.duration_sec||0}s</div>
    <div class='k'>Diff</div><div class='v'>+${plus} -${minus} ~${mod}</div>
    <div class='k'>Flags</div>
    <div><span class='pill'>status: ${esc(t.status||'-')}</span><span class='pill'>oracle: ${t.oracle_used ? 'yes' : 'no'}</span><span class='pill'>remote: ${esc(t.remote_status||'-')}</span></div>
    <div class='k'>Open in CLI</div>
    <div class='cmd'>cloudmem thread show ${esc(t.thread_id)}</div>
  `;
  document.getElementById('right').innerHTML = html;
}

function renderEvents(events){
  const el=document.getElementById('events');
  if(!events.length){ el.innerHTML = "<div class='muted'>No events recorded.</div>"; return; }
  el.innerHTML = events.map(ev => `
    <div class='card'>
      <div class='ev-title'>${esc(ev.saved_at || '')}</div>
      <div class='ev-body'>${esc(JSON.stringify(ev.event ?? ev, null, 2))}</div>
    </div>
  `).join('');
}

async function openThread(id){
  const data = await j('/api/thread/' + encodeURIComponent(id));
  if(!data.thread) return;
  const t=data.thread;
  document.getElementById('title').textContent = t.thread_id;
  document.getElementById('subtitle').textContent = `${t.repo||'-'} • ${t.branch||'-'} • ${t.ended_at||''}`;
  renderRight(t);
  renderEvents(data.events || []);
  [...document.querySelectorAll('.thread-item')].forEach(n=>n.classList.remove('active'));
  const cur=document.querySelector(`[data-id="${CSS.escape(id)}"]`);
  if(cur) cur.classList.add('active');
}

async function boot(){
  const data = await j('/api/threads?limit=200');
  const rows = data.threads || [];
  const left=document.getElementById('left');
  left.innerHTML = rows.map((t,i)=>`
    <div class='thread-item ${i===0?'active':''}' data-id='${esc(t.thread_id)}' onclick='openThread(${JSON.stringify(String(t.thread_id))})'>
      <div style='font-weight:600;'>${esc(t.thread_id)}</div>
      <div class='muted'>${esc(t.repo||'-')} / ${esc(t.branch||'-')}</div>
      <div class='muted'>${esc(t.status||'-')} • ${esc(t.ended_at||'')}</div>
    </div>
  `).join('') || "<div class='muted' style='padding:12px'>No threads yet.</div>";
  if(rows.length) openThread(rows[0].thread_id);
}
boot();
</script>
</body>
</html>"""


class ThreadUIHandler(BaseHTTPRequestHandler):
    def _json(self, payload: dict, status: int = 200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html: str, status: int = 200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._html(_ui_html())
            return

        if path == "/api/threads":
            q = parse_qs(parsed.query)
            try:
                limit = int((q.get("limit") or ["50"])[0])
            except Exception:
                limit = 50
            rows = list_threads(limit=max(1, min(500, limit)))
            self._json({"threads": rows, "count": len(rows)})
            return

        if path.startswith("/api/thread/"):
            thread_id = unquote(path.split("/api/thread/", 1)[1])
            row = load_thread(thread_id)
            if row is None:
                self._json({"error": "thread_not_found"}, status=404)
                return
            events = load_thread_events(thread_id, limit=500)
            self._json({"thread": row, "events": events})
            return

        self._json({"error": "not_found"}, status=404)


def serve_threads(host: str = "127.0.0.1", port: int = 8788):
    server = ThreadingHTTPServer((host, int(port)), ThreadUIHandler)
    print(f"CloudMem thread UI: http://{host}:{port}")
    server.serve_forever()
