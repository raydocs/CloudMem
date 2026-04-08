"""Thread ledger: AMP-style per-session logs with optional remote upload hooks."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import time
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import get_cloudmem_home

THREADS_DIR = "threads"
EVENTS_FILE = "events.jsonl"
INDEX_FILE = "index.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _thread_home(home: str | Path | None = None) -> Path:
    root = Path(home) if home else get_cloudmem_home()
    p = root / THREADS_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def _daily_dir(ts_iso: str, home: str | Path | None = None) -> Path:
    dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    p = _thread_home(home) / f"{dt.year:04d}" / f"{dt.month:02d}" / f"{dt.day:02d}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _run_git(args: list[str], cwd: str | None = None) -> tuple[bool, str]:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False, ""
    if out.returncode != 0:
        return False, (out.stderr or "").strip()
    return True, (out.stdout or "").strip()


def _git_context(cwd: str | None = None) -> dict[str, Any]:
    ok_repo, _ = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=cwd)
    if not ok_repo:
        return {
            "repo": Path(cwd or os.getcwd()).name,
            "branch": "",
            "git": False,
            "lines_added": 0,
            "lines_deleted": 0,
            "lines_modified": 0,
            "files_changed": 0,
        }

    _ok, root = _run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
    ok_branch, branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    ok_stat, stat = _run_git(["diff", "--numstat"], cwd=cwd)

    added = 0
    deleted = 0
    modified = 0
    files = 0
    if ok_stat and stat:
        for line in stat.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            a_raw, d_raw, _path = parts[0], parts[1], parts[2]
            a = 0 if a_raw == "-" else _safe_int(a_raw)
            d = 0 if d_raw == "-" else _safe_int(d_raw)
            added += a
            deleted += d
            modified += min(a, d)
            files += 1

    return {
        "repo": Path(root).name if root else Path(cwd or os.getcwd()).name,
        "branch": branch if ok_branch else "",
        "git": True,
        "lines_added": added,
        "lines_deleted": deleted,
        "lines_modified": modified,
        "files_changed": files,
    }


def _token_cost(hook_data: dict[str, Any], env: dict[str, str] | None = None) -> tuple[int, int, float, bool]:
    env = env or os.environ
    token_in = _safe_int(
        hook_data.get("token_input")
        or hook_data.get("tokens_in")
        or hook_data.get("prompt_tokens")
        or hook_data.get("input_tokens")
    )
    token_out = _safe_int(
        hook_data.get("token_output")
        or hook_data.get("tokens_out")
        or hook_data.get("completion_tokens")
        or hook_data.get("output_tokens")
    )

    # exact cost if caller provided one
    exact_cost = hook_data.get("cost_usd")
    if exact_cost is not None:
        return token_in, token_out, round(_safe_float(exact_cost), 6), False

    # otherwise estimate from env rate config
    in_rate = _safe_float(env.get("CLOUDMEM_COST_PER_1K_INPUT"), 0.0)
    out_rate = _safe_float(env.get("CLOUDMEM_COST_PER_1K_OUTPUT"), 0.0)
    if in_rate <= 0 and out_rate <= 0:
        return token_in, token_out, 0.0, True

    estimated = ((token_in / 1000.0) * in_rate) + ((token_out / 1000.0) * out_rate)
    return token_in, token_out, round(estimated, 6), True


def _prompt_count(hook_data: dict[str, Any]) -> int:
    v = hook_data.get("prompt_count") or hook_data.get("prompts")
    if v is not None:
        return _safe_int(v)

    transcript = hook_data.get("transcript_text")
    if isinstance(transcript, str) and transcript:
        # Heuristic for exported transcript formats with user turns prefixed by ">"
        return len([ln for ln in transcript.splitlines() if ln.lstrip().startswith(">")])
    return 0


def _duration_sec(hook_data: dict[str, Any], now_iso: str) -> int:
    started = hook_data.get("started_at") or hook_data.get("session_started_at")
    ended = hook_data.get("ended_at") or hook_data.get("session_ended_at") or now_iso
    if not started:
        return _safe_int(hook_data.get("duration_sec") or hook_data.get("duration_seconds"), 0)
    try:
        s = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        e = datetime.fromisoformat(str(ended).replace("Z", "+00:00"))
        return max(0, int((e - s).total_seconds()))
    except Exception:
        return _safe_int(hook_data.get("duration_sec") or hook_data.get("duration_seconds"), 0)


def _bool_from_any(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(v)


@dataclass
class ThreadRecord:
    thread_id: str
    session_id: str
    status: str
    created_at: str
    ended_at: str
    duration_sec: int
    repo: str
    branch: str
    mode: str
    interface: str
    prompt_count: int
    token_input: int
    token_output: int
    context_used_pct: float
    cost_usd: float
    cost_is_estimated: bool
    lines_added: int
    lines_deleted: int
    lines_modified: int
    files_changed: int
    oracle_used: bool
    tool_calls_count: int
    transcript_path: str
    commit_sha: str
    sync_status: str
    ingest_status: str
    error_code: str
    error_detail: str
    remote_status: str


def build_thread_record(
    *,
    session_id: str,
    hook_data: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
    status: str,
    error_code: str = "",
    error_detail: str = "",
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> ThreadRecord:
    hook_data = hook_data or {}
    manifest = manifest or {}
    env = env or os.environ
    now_iso = _utc_now()

    git = _git_context(cwd=cwd)
    token_in, token_out, cost_usd, cost_is_estimated = _token_cost(hook_data, env=env)

    context_pct = _safe_float(
        hook_data.get("context_used_pct")
        or hook_data.get("context_usage_pct")
        or hook_data.get("context_percent")
        or 0.0
    )

    sync = manifest.get("sync") or {}
    ingest = manifest.get("ingest") or {}

    thread_id = str(
        hook_data.get("thread_id")
        or hook_data.get("threadId")
        or hook_data.get("conversation_id")
        or session_id
    )

    return ThreadRecord(
        thread_id=thread_id,
        session_id=str(session_id),
        status=status,
        created_at=str(hook_data.get("started_at") or hook_data.get("session_started_at") or now_iso),
        ended_at=str(hook_data.get("ended_at") or hook_data.get("session_ended_at") or now_iso),
        duration_sec=_duration_sec(hook_data, now_iso),
        repo=str(hook_data.get("repo") or git["repo"]),
        branch=str(hook_data.get("branch") or git["branch"]),
        mode=str(hook_data.get("mode") or hook_data.get("run_mode") or ""),
        interface=str(hook_data.get("interface") or hook_data.get("client") or "CLI"),
        prompt_count=_prompt_count(hook_data),
        token_input=token_in,
        token_output=token_out,
        context_used_pct=round(context_pct, 3),
        cost_usd=cost_usd,
        cost_is_estimated=cost_is_estimated,
        lines_added=_safe_int(hook_data.get("lines_added"), git["lines_added"]),
        lines_deleted=_safe_int(hook_data.get("lines_deleted"), git["lines_deleted"]),
        lines_modified=_safe_int(hook_data.get("lines_modified"), git["lines_modified"]),
        files_changed=_safe_int(hook_data.get("files_changed"), git["files_changed"]),
        oracle_used=_bool_from_any(hook_data.get("oracle_used") or hook_data.get("uses_oracle") or False),
        tool_calls_count=_safe_int(hook_data.get("tool_calls_count") or hook_data.get("tool_calls") or 0),
        transcript_path=str(hook_data.get("transcript_path") or hook_data.get("transcriptPath") or ""),
        commit_sha=str(sync.get("commit_sha") or ""),
        sync_status=str(sync.get("status") or "pending"),
        ingest_status=str(ingest.get("status") or "pending"),
        error_code=error_code,
        error_detail=error_detail,
        remote_status="pending",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _thread_file(thread_id: str, home: str | Path | None = None) -> Path:
    return _thread_home(home) / f"{thread_id}.json"


def save_thread_record(
    record: ThreadRecord,
    *,
    raw_event: dict[str, Any] | None = None,
    home: str | Path | None = None,
) -> dict[str, Any]:
    payload = asdict(record)
    payload["saved_at"] = _utc_now()

    thread_path = _thread_file(record.thread_id, home=home)
    thread_path.parent.mkdir(parents=True, exist_ok=True)
    thread_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    daily = _daily_dir(payload["saved_at"], home=home)
    _append_jsonl(daily / INDEX_FILE, payload)

    if raw_event is not None:
        _append_jsonl(daily / EVENTS_FILE, {
            "thread_id": record.thread_id,
            "session_id": record.session_id,
            "saved_at": payload["saved_at"],
            "event": raw_event,
        })

    return payload


def set_thread_remote_status(
    thread_id: str,
    *,
    remote_status: str,
    remote_detail: str = "",
    home: str | Path | None = None,
) -> dict[str, Any] | None:
    row = load_thread(thread_id, home=home)
    if row is None:
        return None
    row["remote_status"] = remote_status
    if remote_detail:
        row["remote_detail"] = remote_detail
    row["updated_at"] = _utc_now()
    path = _thread_file(thread_id, home=home)
    path.write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


def load_thread(thread_id: str, *, home: str | Path | None = None) -> dict[str, Any] | None:
    path = _thread_file(thread_id, home=home)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_threads(*, limit: int = 20, home: str | Path | None = None) -> list[dict[str, Any]]:
    root = _thread_home(home)
    rows = []
    for p in root.glob("*.json"):
        try:
            rows.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    rows.sort(key=lambda x: str(x.get("ended_at") or x.get("saved_at") or ""), reverse=True)
    return rows[: max(1, limit)]


def load_thread_events(
    thread_id: str,
    *,
    limit: int = 200,
    home: str | Path | None = None,
) -> list[dict[str, Any]]:
    root = _thread_home(home)
    events: list[dict[str, Any]] = []
    for p in root.glob("**/events.jsonl"):
        try:
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    if str(row.get("thread_id", "")) == str(thread_id):
                        events.append(row)
        except Exception:
            continue

    events.sort(key=lambda x: str(x.get("saved_at") or ""))
    if limit > 0:
        events = events[-limit:]
    return events


def format_thread_line(row: dict[str, Any]) -> str:
    thread = row.get("thread_id", "?")
    repo = row.get("repo", "")
    branch = row.get("branch", "")
    mode = row.get("mode", "")
    status = row.get("status", "")
    duration = _safe_int(row.get("duration_sec"), 0)
    prompts = _safe_int(row.get("prompt_count"), 0)
    pct = _safe_float(row.get("context_used_pct"), 0.0)
    cost = _safe_float(row.get("cost_usd"), 0.0)
    plus = _safe_int(row.get("lines_added"), 0)
    minus = _safe_int(row.get("lines_deleted"), 0)
    mod = _safe_int(row.get("lines_modified"), 0)

    return (
        f"{thread} | {repo}:{branch} | {mode or '-'} | {status} | "
        f"{duration}s | {prompts} prompts | {pct:.1f}% ctx | ${cost:.4f} | +{plus}/-{minus}/~{mod}"
    )


def _hmac_signature(secret: str, body: bytes, timestamp: str) -> str:
    msg = timestamp.encode("utf-8") + b"." + body
    digest = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def upload_thread_record(
    payload: dict[str, Any],
    *,
    env: dict[str, str] | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    env = env or os.environ
    endpoint = (env.get("CLOUDMEM_THREAD_REMOTE_URL") or "").strip()
    if not endpoint:
        return {"ok": False, "skipped": True, "reason": "no_remote_url"}

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "cloudmem-thread-ledger/1.0",
    }

    token = (env.get("CLOUDMEM_THREAD_REMOTE_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    timestamp = str(int(time.time()))
    headers["X-Timestamp"] = timestamp

    hmac_secret = (env.get("CLOUDMEM_THREAD_REMOTE_HMAC_SECRET") or "").strip()
    if hmac_secret:
        headers["X-Signature"] = _hmac_signature(hmac_secret, body, timestamp)

    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw) if raw else {}
            except Exception:
                data = {"raw": raw}
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}
