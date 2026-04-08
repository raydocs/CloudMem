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
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;background:#fff;color:#111827;line-height:1.6}
    a{color:#6366f1;text-decoration:none} a:hover{text-decoration:underline}
    .nav{height:52px;border-bottom:1px solid #e5e7eb;display:flex;align-items:center;padding:0 24px;position:sticky;top:0;z-index:100;background:#fff}
    .logo{font-weight:800;font-size:18px;color:#6366f1;letter-spacing:-.4px;cursor:pointer} .logo span{color:#111827}
    .nav-link{margin-left:24px;font-size:14px;color:#6b7280}

    /* List */
    .list-view{max-width:860px;margin:0 auto;padding:32px 24px}
    .list-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
    .list-header h1{font-size:22px;font-weight:700}
    .list-header .count{font-size:14px;color:#6b7280}
    .list-filters{margin-bottom:16px}
    .list-filters input{width:100%;border:1px solid #e5e7eb;border-radius:8px;padding:7px 12px;font:inherit;font-size:13px;outline:none}
    .list-filters input:focus{border-color:#6366f1}
    .trow{display:grid;grid-template-columns:1fr 150px 100px 80px 90px;gap:12px;padding:12px 16px;border-bottom:1px solid #f0f1f3;align-items:center;cursor:pointer;border-radius:10px;transition:background .12s}
    .trow:hover{background:#f9fafb}
    .trow-head{font-size:12px;font-weight:600;color:#9ca3af;cursor:default;border-bottom:2px solid #e5e7eb}
    .trow-head:hover{background:transparent}
    .tid{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .tmeta{font-size:12px;color:#6b7280}
    .pill{font-size:11px;padding:2px 8px;border-radius:999px;font-weight:600;display:inline-block}
    .pill-ok{background:#f0fdf4;color:#16a34a}
    .pill-err{background:#fef2f2;color:#dc2626}
    .pill-mode{background:#eef2ff;color:#6366f1}

    /* Detail */
    .detail-view{display:none}
    .detail-layout{display:grid;grid-template-columns:1fr 300px;min-height:calc(100vh - 52px)}
    .center{max-width:800px;padding:40px 32px 80px;margin:0 auto}
    .back{font-size:13px;color:#6b7280;display:inline-flex;align-items:center;gap:4px;margin-bottom:20px;cursor:pointer} .back:hover{color:#111}
    .d-title{font-size:26px;font-weight:700;letter-spacing:-.4px;text-align:center}
    .d-author{text-align:center;margin-top:8px;font-size:14px;color:#6b7280}
    .stat-row{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px;padding:16px;background:#f9fafb;border-radius:12px;border:1px solid #e5e7eb}
    .stat-item{text-align:center;flex:1;min-width:80px} .stat-item .sv{font-size:18px;font-weight:700} .stat-item .sl{font-size:11px;color:#9ca3af;margin-top:2px}
    .timeline{margin-top:32px}
    .t-msg{display:flex;gap:14px;margin-bottom:24px}
    .t-avatar{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;margin-top:2px;background:#e0e7ff}
    .t-body{flex:1;min-width:0} .t-role{font-size:12px;font-weight:600;color:#6b7280;margin-bottom:4px} .t-text{font-size:14px;color:#374151;line-height:1.7}
    .t-tool{background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;margin-bottom:12px;overflow:hidden}
    .t-tool-head{display:flex;align-items:center;gap:8px;padding:10px 14px;cursor:pointer;font-size:13px} .t-tool-head:hover{background:#f3f4f6}
    .t-tool-name{font-weight:600;color:#374151} .t-tool-desc{color:#9ca3af;font-size:12px}
    .t-tool-chevron{margin-left:auto;color:#9ca3af;transition:transform .2s} .t-tool-chevron.open{transform:rotate(180deg)}
    .t-tool-body{display:none;border-top:1px solid #e5e7eb;padding:12px 14px;background:#fafbfc} .t-tool-body.open{display:block}
    .t-tool-body pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;white-space:pre-wrap;word-break:break-all;color:#334155;line-height:1.6}
    .ev-card{background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;margin-bottom:8px;overflow:hidden}
    .ev-head{display:flex;align-items:center;gap:8px;padding:10px 14px;cursor:pointer;font-size:13px} .ev-head:hover{background:#f3f4f6}
    .ev-time{font-size:12px;color:#9ca3af} .ev-label{font-weight:600;color:#374151}
    .ev-chevron{margin-left:auto;color:#9ca3af;transition:transform .2s} .ev-chevron.open{transform:rotate(180deg)}
    .ev-body{display:none;border-top:1px solid #e5e7eb;padding:12px 14px;background:#fafbfc} .ev-body.open{display:block}
    .ev-body pre{font-family:ui-monospace,monospace;font-size:12px;white-space:pre-wrap;word-break:break-all;color:#334155;line-height:1.6}
    .diff-a{color:#16a34a;font-weight:600} .diff-d{color:#dc2626;font-weight:600} .diff-m{color:#ca8a04;font-weight:600}
    .sidebar{border-left:1px solid #e5e7eb;padding:24px 20px;background:#fff;position:sticky;top:52px;height:calc(100vh - 52px);overflow-y:auto}
    .sb-badge{display:inline-flex;align-items:center;gap:4px;font-size:12px;color:#6b7280;border:1px solid #e5e7eb;border-radius:999px;padding:3px 10px;margin-bottom:16px}
    .sb-title{font-size:14px;font-weight:700;margin-bottom:14px}
    .sb-row{display:flex;gap:10px;margin-bottom:11px;font-size:13px;line-height:1.4}
    .sb-icon{width:18px;text-align:center;flex-shrink:0;font-size:14px} .sb-val{color:#111827;font-weight:500;word-break:break-all}
    .sb-section{margin-top:20px;padding-top:16px;border-top:1px solid #f0f1f3}
    .sb-label-title{font-size:13px;font-weight:700;margin-bottom:8px}
    .cli-box{background:#f4f4f7;border:1px solid #e5e7eb;border-radius:8px;padding:8px 10px;font-family:ui-monospace,monospace;font-size:12px;color:#6b7280}
    .empty{text-align:center;padding:60px 20px;color:#9ca3af} .empty .e-icon{font-size:40px;margin-bottom:12px}
    @media(max-width:900px){.detail-layout{grid-template-columns:1fr} .sidebar{display:none}}
  </style>
</head>
<body>
<nav class="nav"><div class="logo" onclick="showList()">Cloud<span>Mem</span></div><a class="nav-link" href="#" onclick="showList();return false">ud83euddf5 Threads</a></nav>

<div id="listView" class="list-view">
  <div class="list-header"><h1>Threads</h1><div class="count" id="listCount"></div></div>
  <div class="list-filters"><input id="search" placeholder="Search thread, repo, branchu2026" /></div>
  <div id="listBody"><div class="empty"><div class="e-icon">u23f3</div>Loadingu2026</div></div>
</div>

<div id="detailView" class="detail-view">
  <div class="detail-layout">
    <div><div class="center" id="centerCol"></div></div>
    <div class="sidebar" id="sidebarCol"></div>
  </div>
</div>

<script>
let allRows=[],activeId=null;
function n(x){return Number(x||0)}
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function fN(v){v=n(v);if(v>=1e6)return(v/1e6).toFixed(1)+'M';if(v>=1e3)return(v/1e3).toFixed(1)+'k';return String(v)}
function fD(s){s=n(s);if(s<60)return s+'s';if(s<3600)return Math.floor(s/60)+'m '+s%60+'s';const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h+'h '+m+'m'}
function ago(iso){if(!iso)return'-';const d=(Date.now()-new Date(iso).getTime())/1e3;if(d<60)return'just now';if(d<3600)return Math.floor(d/60)+'m ago';if(d<86400)return Math.floor(d/3600)+'h ago';if(d<604800)return Math.floor(d/86400)+'d ago';return new Date(iso).toLocaleDateString()}
function showList(){document.getElementById('listView').style.display='';document.getElementById('detailView').style.display='none'}
function showDetail(){document.getElementById('listView').style.display='none';document.getElementById('detailView').style.display=''}
async function j(url){const r=await fetch(url);return await r.json()}

function renderList(){
  const q=document.getElementById('search').value.trim().toLowerCase();
  const rows=q?allRows.filter(r=>`${r.thread_id||''} ${r.repo||''} ${r.branch||''}`.toLowerCase().includes(q)):allRows;
  document.getElementById('listCount').textContent=`${rows.length} threads`;
  const el=document.getElementById('listBody');
  if(!rows.length){el.innerHTML='<div class="empty"><div class="e-icon">ud83dudced</div>No threads</div>';return;}
  el.innerHTML='<div class="trow trow-head"><span>Thread</span><span>Repo</span><span>Status</span><span>Diff</span><span>Time</span></div>'+rows.map(r=>{
    const sc=r.status==='completed'?'pill-ok':r.status==='failed'?'pill-err':'pill-mode';
    const plus=n(r.lines_added),minus=n(r.lines_deleted);
    return`<div class="trow" data-id="${esc(r.thread_id)}"><div><div class="tid">${esc(r.thread_id)}</div><div class="tmeta">${esc(r.branch||'-')}</div></div><div class="tmeta">${esc(r.repo||'-')}</div><div><span class="pill ${sc}">${esc(r.status||'?')}</span></div><div class="tmeta"><span class="diff-a">+${fN(plus)}</span> <span class="diff-d">-${fN(minus)}</span></div><div class="tmeta">${ago(r.ended_at)}</div></div>`;}).join('');
  el.querySelectorAll('.trow:not(.trow-head)').forEach(n=>n.addEventListener('click',()=>openThread(n.dataset.id)));
}

async function openThread(id){
  activeId=id;showDetail();
  const data=await j('/api/thread/'+encodeURIComponent(id));
  if(!data.thread)return;
  const t=data.thread,events=data.events||[];
  const plus=n(t.lines_added),minus=n(t.lines_deleted),mod=n(t.lines_modified),tokIn=n(t.token_input),tokOut=n(t.token_output);

  let eventsHtml='';
  if(events.length){
    eventsHtml='<div style="margin-top:24px"><div style="font-size:14px;font-weight:600;margin-bottom:12px">Events</div>'+events.map((ev,i)=>{
      const label=ev.event?.status||'event';
      return`<div class="ev-card"><div class="ev-head" onclick="this.nextElementSibling.classList.toggle('open');this.querySelector('.ev-chevron').classList.toggle('open')"><span style="font-size:14px">ud83dudd39</span><span class="ev-label">${esc(label)}</span><span class="ev-time">${esc(ev.saved_at||'')}</span><span class="ev-chevron">u25be</span></div><div class="ev-body"><pre>${esc(JSON.stringify(ev.event??ev,null,2))}</pre></div></div>`;}).join('')+'</div>';
  }

  document.getElementById('centerCol').innerHTML=`
    <div class="back" onclick="showList()">u2190 Back to Threads</div>
    <div class="d-title">${esc(t.repo||t.thread_id)}</div>
    <div class="d-author">${esc(t.branch||'-')} \u00b7 ${esc(t.mode||'CLI')} \u00b7 ${ago(t.ended_at)}</div>
    <div class="stat-row">
      <div class="stat-item"><div class="sv">${fD(t.duration_sec)}</div><div class="sl">Duration</div></div>
      <div class="stat-item"><div class="sv">${n(t.prompt_count)}</div><div class="sl">Prompts</div></div>
      <div class="stat-item"><div class="sv">${fN(tokIn+tokOut)}</div><div class="sl">Tokens</div></div>
      <div class="stat-item"><div class="sv">$${n(t.cost_usd).toFixed(2)}</div><div class="sl">Cost</div></div>
      <div class="stat-item"><div class="sv">${n(t.context_used_pct).toFixed(0)}%</div><div class="sl">Context</div></div>
    </div>
    <div class="timeline">
      ${plus||minus||mod?`<div class="t-tool"><div class="t-tool-head" onclick="this.nextElementSibling.classList.toggle('open');this.querySelector('.t-tool-chevron').classList.toggle('open')"><span style="font-size:14px">ud83dudcdd</span><span class="t-tool-name">Code Changes</span><span class="t-tool-desc"><span class="diff-a">+${fN(plus)}</span> <span class="diff-d">-${fN(minus)}</span> <span class="diff-m">~${fN(mod)}</span> lines \u00b7 ${n(t.files_changed)} files</span><span class="t-tool-chevron">\u25be</span></div><div class="t-tool-body"><pre>Files changed: ${n(t.files_changed)}\nLines added:   ${plus}\nLines deleted: ${minus}\nLines modified:${mod}\nCommit: ${esc(t.commit_sha||'-')}</pre></div></div>`:''}
      ${t.error_code?`<div class="t-msg"><div class="t-avatar" style="background:#fef2f2">u26a0ufe0f</div><div class="t-body"><div class="t-role">Error</div><div class="t-text" style="color:#dc2626">${esc(t.error_code)}: ${esc(t.error_detail||'')}</div></div></div>`:''}
      <div class="t-msg"><div class="t-avatar">ud83eudd16</div><div class="t-body"><div class="t-role">Session Summary</div><div class="t-text">Worked for <strong>${fD(t.duration_sec)}</strong> on <strong>${esc(t.repo||'-')}</strong> (${esc(t.branch||'-')}). Processed <strong>${n(t.prompt_count)}</strong> prompts using <strong>${fN(tokIn+tokOut)}</strong> tokens. ${plus||minus?`Changed <strong>${n(t.files_changed)}</strong> files (<span class="diff-a">+${fN(plus)}</span> <span class="diff-d">-${fN(minus)}</span>).`:''} ${n(t.oracle_used)?'<strong>Oracle</strong> was consulted.':''} Ingest: <strong>${esc(t.ingest_status||'-')}</strong>. Sync: <strong>${esc(t.sync_status||'-')}</strong>.</div></div></div>
    </div>
    ${eventsHtml}
  `;

  document.getElementById('sidebarCol').innerHTML=`
    <div class="sb-badge">\ud83d\udd17 ${esc(t.status||'unknown')}</div>
    <div class="sb-title">Thread</div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udcc5</span><span class="sb-val">${ago(t.ended_at)}</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udcc1</span><span class="sb-val">${esc(t.repo||'-')}</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udd00</span><span class="sb-val">${esc(t.branch||'-')}</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83e\udde0</span><span class="sb-val">${esc(t.mode||'-')}</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udcb0</span><span class="sb-val">$${n(t.cost_usd).toFixed(2)}${t.cost_is_estimated?' (est.)':''}</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udcbb</span><span class="sb-val">${esc(t.interface||'CLI')}</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udcac</span><span class="sb-val">${n(t.prompt_count)} prompts</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udcca</span><span class="sb-val">${n(t.context_used_pct).toFixed(1)}%</span></div>
    <div class="sb-row"><span class="sb-icon">\u23f1\ufe0f</span><span class="sb-val">Worked for ${fD(t.duration_sec)}</span></div>
    <div class="sb-row"><span class="sb-icon">\ud83d\udcdd</span><span class="sb-val"><span class="diff-a">+${fN(plus)}</span> <span class="diff-d">-${fN(minus)}</span> <span class="diff-m">~${fN(mod)}</span> lines</span></div>
    ${n(t.oracle_used)?'<div class="sb-row"><span class="sb-icon">\ud83d\udd2e</span><span class="sb-val">Uses Oracle</span></div>':''}
    <div class="sb-section"><div class="sb-label-title">Open in CLI</div><div class="cli-box">cloudmem thread show ${esc(t.thread_id)}</div></div>
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
