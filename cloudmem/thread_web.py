"""Local web UI for CloudMem thread views u2014 Amp-inspired design."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from .thread_ledger import list_threads, load_thread, load_thread_events


def _ui_html() -> str:
    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CloudMem u00b7 Threads</title>
  <style>
    :root {
      --bg: #f8f9fb;
      --surface: #ffffff;
      --border: #e5e7eb;
      --border-light: #f0f1f3;
      --text: #111827;
      --text-s: #6b7280;
      --text-m: #9ca3af;
      --brand: #6366f1;
      --brand-light: #eef2ff;
      --green: #16a34a;
      --red: #dc2626;
      --amber: #ca8a04;
      --green-bg: #f0fdf4;
      --red-bg: #fef2f2;
      --radius: 12px;
      --shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; }
    .mono { font-family: ui-monospace,SFMono-Regular,Menlo,monospace; }

    .nav { height:52px; background:var(--surface); border-bottom:1px solid var(--border); display:flex; align-items:center; padding:0 20px; position:sticky; top:0; z-index:100; }
    .nav-logo { font-weight:700; font-size:16px; color:var(--brand); letter-spacing:-0.3px; }
    .nav-logo span { color:var(--text); }
    .nav-link { margin-left:20px; font-size:14px; color:var(--text-s); text-decoration:none; }

    .layout { display:grid; grid-template-columns:320px 1fr 280px; height:calc(100vh - 52px); }

    .panel-left { border-right:1px solid var(--border); background:var(--surface); display:flex; flex-direction:column; overflow:hidden; }
    .filters { padding:12px; border-bottom:1px solid var(--border-light); }
    .filters input { width:100%; border:1px solid var(--border); border-radius:8px; padding:7px 10px; font:inherit; font-size:13px; outline:none; }
    .filters input:focus { border-color:var(--brand); }
    .thread-list { flex:1; overflow-y:auto; }
    .thread-item { padding:12px 14px; border-bottom:1px solid var(--border-light); cursor:pointer; border-left:3px solid transparent; transition:all .15s; }
    .thread-item:hover { background:#f9fafb; }
    .thread-item.active { background:var(--brand-light); border-left-color:var(--brand); }
    .thread-id { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .thread-meta { font-size:12px; color:var(--text-m); margin-top:3px; }
    .thread-badges { display:flex; gap:5px; margin-top:5px; }
    .badge { font-size:11px; padding:1px 7px; border-radius:999px; font-weight:600; }
    .badge-ok { background:var(--green-bg); color:var(--green); }
    .badge-err { background:var(--red-bg); color:var(--red); }
    .badge-mode { background:#f0f0ff; color:var(--brand); }

    .panel-center { overflow-y:auto; padding:24px 28px; }
    .detail-title { font-size:22px; font-weight:700; letter-spacing:-0.3px; }
    .detail-sub { font-size:13px; color:var(--text-s); margin-top:4px; }
    .stat-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-top:20px; }
    .stat-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:14px; box-shadow:var(--shadow); }
    .stat-label { font-size:12px; color:var(--text-m); font-weight:500; }
    .stat-value { font-size:20px; font-weight:700; margin-top:4px; }
    .stat-sub { font-size:12px; color:var(--text-m); margin-top:2px; }
    .diff-add { color:var(--green); } .diff-del { color:var(--red); } .diff-mod { color:var(--amber); }
    .diff-line { display:flex; gap:10px; font-size:14px; font-weight:600; font-family:ui-monospace,monospace; }
    .progress-bar { height:6px; background:var(--border); border-radius:999px; overflow:hidden; margin-top:6px; }
    .progress-fill { height:100%; background:var(--brand); border-radius:999px; }

    .events-section { margin-top:24px; }
    .ev-title { font-size:14px; font-weight:600; margin-bottom:12px; }
    .ev-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:12px; margin-bottom:8px; box-shadow:var(--shadow); }
    .ev-time { font-size:11px; color:var(--text-m); margin-bottom:6px; }
    .ev-body { font-family:ui-monospace,monospace; font-size:12px; white-space:pre-wrap; word-break:break-all; color:#334155; max-height:200px; overflow:auto; }

    .panel-right { border-left:1px solid var(--border); background:var(--surface); overflow-y:auto; padding:20px; }
    .sb-title { font-size:13px; font-weight:700; margin-bottom:12px; }
    .sb-row { display:flex; align-items:flex-start; gap:8px; margin-bottom:10px; font-size:13px; }
    .sb-icon { width:18px; text-align:center; font-size:14px; flex-shrink:0; }
    .sb-val { color:var(--text); font-weight:500; word-break:break-all; }
    .cli-box { background:#f4f4f7; border:1px solid var(--border); border-radius:8px; padding:8px 10px; font-family:ui-monospace,monospace; font-size:12px; color:var(--text-s); margin-top:12px; }
    .empty { display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; color:var(--text-m); font-size:14px; gap:8px; }
    .empty .icon { font-size:32px; }

    @media(max-width:1024px){ .layout{grid-template-columns:280px 1fr;} .panel-right{display:none;} }
    @media(max-width:768px){ .layout{grid-template-columns:1fr;height:auto;} .panel-left{max-height:40vh;} }
  </style>
</head>
<body>
  <nav class="nav">
    <div class="nav-logo">u2601ufe0f Cloud<span>Mem</span></div>
    <a class="nav-link" href="#">ud83euddf5 Threads</a>
  </nav>

  <div class="layout">
    <div class="panel-left">
      <div class="filters"><input id="search" placeholder="Search threadsu2026" /></div>
      <div class="thread-list" id="threadList"><div class="empty"><div class="icon">ud83euddf5</div>Loadingu2026</div></div>
    </div>
    <div class="panel-center" id="center"><div class="empty" style="padding-top:100px"><div class="icon">ud83dudccb</div>Select a thread</div></div>
    <div class="panel-right" id="sidebar"><div class="empty"><div class="icon">ud83dudccc</div>No thread selected</div></div>
  </div>

<script>
let allRows=[], activeId=null;
function n(x){return Number(x||0);}
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function fmtNum(v){v=n(v);if(v>=1e6)return(v/1e6).toFixed(1)+'M';if(v>=1e3)return(v/1e3).toFixed(1)+'k';return String(v);}
function fmtDur(s){s=n(s);if(s<60)return s+'s';if(s<3600)return Math.floor(s/60)+'m '+s%60+'s';return Math.floor(s/3600)+'h '+Math.floor(s%3600/60)+'m';}
function timeAgo(iso){if(!iso)return'-';const d=(Date.now()-new Date(iso).getTime())/1e3;if(d<60)return'now';if(d<3600)return Math.floor(d/60)+'m ago';if(d<86400)return Math.floor(d/3600)+'h ago';if(d<604800)return Math.floor(d/86400)+'d ago';return new Date(iso).toLocaleDateString();}

async function j(url){const r=await fetch(url);return await r.json();}

function renderList(){
  const q=document.getElementById('search').value.trim().toLowerCase();
  const rows=q?allRows.filter(r=>`${r.thread_id||''} ${r.repo||''} ${r.branch||''}`.toLowerCase().includes(q)):allRows;
  const el=document.getElementById('threadList');
  if(!rows.length){el.innerHTML='<div class="empty"><div class="icon">ud83dudced</div>No threads</div>';return;}
  el.innerHTML=rows.map(r=>{
    const cls=activeId===r.thread_id?'active':'';
    const sc=r.status==='completed'?'badge-ok':r.status==='failed'?'badge-err':'badge-mode';
    return `<div class="thread-item ${cls}" data-id="${esc(r.thread_id)}">
      <div class="thread-id">${esc(r.thread_id)}</div>
      <div class="thread-meta">${esc(r.repo||'-')} \u00b7 ${esc(r.branch||'-')} \u00b7 ${timeAgo(r.ended_at)}</div>
      <div class="thread-badges"><span class="badge ${sc}">${esc(r.status||'?')}</span>${r.mode?`<span class="badge badge-mode">${esc(r.mode)}</span>`:''}</div>
    </div>`;}).join('');
  el.querySelectorAll('.thread-item').forEach(n=>n.addEventListener('click',()=>openThread(n.dataset.id)));
}

async function openThread(id){
  activeId=id; renderList();
  const data=await j('/api/thread/'+encodeURIComponent(id));
  if(!data.thread)return;
  const t=data.thread;
  const plus=n(t.lines_added),minus=n(t.lines_deleted),mod=n(t.lines_modified);

  document.getElementById('center').innerHTML=`
    <div class="detail-title">${esc(t.repo||t.thread_id)}</div>
    <div class="detail-sub">${esc(t.repo||'-')} \u00b7 ${esc(t.branch||'-')} \u00b7 ${timeAgo(t.ended_at)}</div>
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-label">Duration</div><div class="stat-value">${fmtDur(t.duration_sec)}</div></div>
      <div class="stat-card"><div class="stat-label">Prompts</div><div class="stat-value">${n(t.prompt_count)}</div><div class="stat-sub">${esc(t.interface||'CLI')}</div></div>
      <div class="stat-card"><div class="stat-label">Cost</div><div class="stat-value">$${n(t.cost_usd).toFixed(2)}</div><div class="stat-sub">${t.cost_is_estimated?'estimated':'actual'}</div></div>
    </div>
    <div class="stat-grid" style="margin-top:12px">
      <div class="stat-card"><div class="stat-label">Context</div><div class="stat-value">${n(t.context_used_pct).toFixed(1)}%</div><div class="progress-bar"><div class="progress-fill" style="width:${Math.min(100,n(t.context_used_pct))}%"></div></div></div>
      <div class="stat-card"><div class="stat-label">Lines Changed</div><div class="stat-value"><div class="diff-line"><span class="diff-add">+${fmtNum(plus)}</span><span class="diff-del">-${fmtNum(minus)}</span><span class="diff-mod">~${fmtNum(mod)}</span></div></div><div class="stat-sub">${n(t.files_changed)} files</div></div>
      <div class="stat-card"><div class="stat-label">Tokens</div><div class="stat-value">${fmtNum(n(t.token_input)+n(t.token_output))}</div><div class="stat-sub">in: ${fmtNum(t.token_input)} \u00b7 out: ${fmtNum(t.token_output)}</div></div>
    </div>
    <div class="events-section"><div class="ev-title">Events</div><div id="eventsArea"></div></div>
  `;
  const events=data.events||[];
  const ea=document.getElementById('eventsArea');
  if(!events.length){ea.innerHTML='<div style="color:var(--text-m);font-size:13px">No events recorded.</div>';}
  else{ea.innerHTML=events.map(ev=>`<div class="ev-card"><div class="ev-time">${esc(ev.saved_at||'')}</div><div class="ev-body">${esc(JSON.stringify(ev.event??ev,null,2))}</div></div>`).join('');}

  document.getElementById('sidebar').innerHTML=`
    <div class="sb-title">Thread</div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udcc5</span><span class="sb-val">${timeAgo(t.ended_at)}</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udcc1</span><span class="sb-val">${esc(t.repo||'-')}</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udd00</span><span class="sb-val">${esc(t.branch||'-')}</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83e\udde0</span><span class="sb-val">${esc(t.mode||'-')}</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udcb0</span><span class="sb-val">$${n(t.cost_usd).toFixed(2)}${t.cost_is_estimated?' (est.)':''}</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udcbb</span><span class="sb-val">${esc(t.interface||'CLI')}</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udcac</span><span class="sb-val">${n(t.prompt_count)} prompts</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udcca</span><span class="sb-val">${n(t.context_used_pct).toFixed(1)}% context</span></div>
    <div class="sb-row"><span class="sb-icon">\u23f1\ufe0f</span><span class="sb-val">${fmtDur(t.duration_sec)}</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udcdd</span><span class="sb-val"><span class="diff-add">+${fmtNum(plus)}</span> <span class="diff-del">-${fmtNum(minus)}</span> <span class="diff-mod">~${fmtNum(mod)}</span> lines</span></div>
    ${n(t.oracle_used)?'<div class="sb-row"><span class="sb-icon">\ud83d\udd2e</span><span class="sb-val">Uses Oracle</span></div>':''}
    <div class="sb-row"><span class="sb-icon">\u2601\ufe0f</span><span class="sb-val">${esc(t.sync_status||t.remote_status||'-')}</span></div>
    <div class="sb-title" style="margin-top:16px">Open in CLI</div>
    <div class="cli-box">cloudmem thread show ${esc(t.thread_id)}</div>
  `;
}

async function boot(){
  const data=await j('/api/threads?limit=200');
  allRows=(data.threads||[]).sort((a,b)=>String(b.ended_at||'').localeCompare(String(a.ended_at||'')));
  renderList();
  if(allRows.length) openThread(allRows[0].thread_id);
}
document.getElementById('search').addEventListener('input', renderList);
boot();
</script>
</body>
</html>"""  # noqa: E501


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
