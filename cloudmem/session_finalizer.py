"""
SessionFinalizer — Orchestrates post-session work:
1. Read Claude Code hook stdin JSON to identify the session
2. Ingest the session transcript into the palace
3. Write a session manifest (for idempotency + Issue↔drawer linkage)
4. Push palace to GitHub (if sync is configured)
"""

import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import get_cloudmem_home, get_palace_path
from .thread_ledger import (
    build_thread_record,
    save_thread_record,
    set_thread_remote_status,
    upload_thread_record,
)

logger = logging.getLogger("cloudmem.finalizer")

SESSIONS_DIR_NAME = "sessions"


class SessionManifest:
    """Persistent record of a single finalized session."""

    def __init__(self, session_id: str, repo_root: str = None):
        self.session_id = session_id
        self._root = Path(repo_root or get_cloudmem_home()) / SESSIONS_DIR_NAME
        self._path = self._root / f"{session_id}.json"
        self._data = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except Exception:
                pass
        return {
            "session_id": self.session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ingest": {"status": "pending"},
            "sync": {"status": "pending"},
            "issue": None,
        }

    def save(self):
        self._root.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2))

    @property
    def is_complete(self) -> bool:
        return self._data.get("ingest", {}).get("status") == "completed"

    @property
    def sync_complete(self) -> bool:
        return self._data.get("sync", {}).get("status") == "pushed"

    def set_ingest(self, **kwargs):
        self._data["ingest"] = {"status": "completed", **kwargs}
        self.save()

    def set_ingest_failed(self, error: str, **details):
        self._data["ingest"] = {"status": "failed", "error": error, **details}
        self.save()

    def set_sync(self, **kwargs):
        self._data["sync"] = {"status": "pushed", **kwargs}
        self.save()

    def set_sync_pending(self, reason: str = ""):
        self._data["sync"] = {"status": "pending", "reason": reason}
        self.save()

    def set_issue(self, repo: str, number: int, url: str):
        self._data["issue"] = {"repo": repo, "number": number, "url": url}
        self.save()

    def to_dict(self) -> dict:
        return dict(self._data)


def _sha256(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception:
        return "unknown"


def _normalize_path(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _find_tracker_state(session_id: str, hooks_dir: str = None) -> dict | None:
    """Try to read session-tracker state file for the session."""
    candidates = []
    hd = hooks_dir or os.path.expanduser("~/.claude/hooks")
    candidates.append(Path(hd) / "state" / f"{session_id}.json")
    candidates.append(Path(hd) / f"{session_id}.json")

    for path in candidates:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
    return None


class SessionFinalizer:
    """Orchestrates post-session ingest and sync."""

    def __init__(self, palace_path: str = None, repo_root: str = None):
        self._palace_path = palace_path or get_palace_path()
        self._repo_root = repo_root or get_cloudmem_home()

    def run(
        self,
        hook_json_stdin: bool = False,
        session_id: str = None,
        transcript_path: str = None,
    ) -> bool:
        """Main entry point. Returns True if ingest succeeded."""

        # 1. Resolve context
        hook_data = {}
        if hook_json_stdin:
            try:
                raw = sys.stdin.read()
                if raw.strip():
                    hook_data = json.loads(raw)
            except Exception:
                pass

        resolved_session_id = (
            session_id
            or hook_data.get("session_id")
            or hook_data.get("sessionId")
            or datetime.now(timezone.utc).strftime("session_%Y%m%d_%H%M%S")
        )

        hook_transcript = hook_data.get("transcript_path")
        if hook_transcript is None:
            hook_transcript = hook_data.get("transcriptPath")

        if transcript_path is not None:
            transcript_input = transcript_path
            transcript_explicit = True
        elif hook_transcript is not None:
            transcript_input = hook_transcript
            transcript_explicit = True
        else:
            transcript_input = None
            transcript_explicit = False

        resolved_transcript = _normalize_path(transcript_input)

        manifest = SessionManifest(resolved_session_id, repo_root=self._repo_root)

        def _finish(
            ok: bool,
            status: str,
            *,
            error_code: str = "",
            error_detail: str = "",
        ) -> bool:
            try:
                record = build_thread_record(
                    session_id=resolved_session_id,
                    hook_data=hook_data,
                    manifest=manifest.to_dict(),
                    status=status,
                    error_code=error_code,
                    error_detail=error_detail,
                    cwd=hook_data.get("cwd") or os.getcwd(),
                )
                payload = save_thread_record(
                    record,
                    raw_event={
                        "hook_json_stdin": hook_json_stdin,
                        "status": status,
                        "error_code": error_code,
                    },
                    home=self._repo_root,
                )
                
                # Add transcript content to payload if available
                if resolved_transcript and Path(resolved_transcript).is_file():
                    try:
                        transcript_content = Path(resolved_transcript).read_text(encoding="utf-8", errors="replace")
                        payload["transcript_content"] = transcript_content
                    except Exception as e:
                        logger.warning(f"Failed to read transcript file: {e}")
                
                remote = upload_thread_record(payload)
                if remote.get("ok"):
                    set_thread_remote_status(
                        record.thread_id,
                        remote_status="uploaded",
                        remote_detail=str(remote.get("status", "200")),
                        home=self._repo_root,
                    )
                elif remote.get("skipped"):
                    set_thread_remote_status(
                        record.thread_id,
                        remote_status="skipped",
                        remote_detail=str(remote.get("reason", "no_remote_url")),
                        home=self._repo_root,
                    )
                else:
                    set_thread_remote_status(
                        record.thread_id,
                        remote_status="failed",
                        remote_detail=str(remote.get("error", "upload_failed")),
                        home=self._repo_root,
                    )
            except Exception as e:
                logger.error(f"Thread ledger write failed: {e}")
            return ok

        # 2. Idempotency: skip repeat ingest, but still retry sync if it is pending.
        skip_ingest = False
        if manifest.is_complete:
            existing_ingest = manifest._data.get("ingest", {})
            existing_sha = existing_ingest.get("transcript_sha256")
            existing_path = _normalize_path(existing_ingest.get("transcript_path"))

            if transcript_explicit and resolved_transcript:
                current_sha = _sha256(resolved_transcript) if Path(resolved_transcript).is_file() else None
                if (existing_sha and current_sha and existing_sha == current_sha) or (
                    existing_path and existing_path == resolved_transcript
                ):
                    if manifest.sync_complete:
                        logger.info(f"Session {resolved_session_id} already finalized, skipping")
                        return _finish(True, "completed")
                    logger.info(
                        f"Session {resolved_session_id} already ingested; retrying pending sync"
                    )
                    skip_ingest = True
            elif not transcript_explicit:
                if manifest.sync_complete:
                    logger.info(
                        f"Session {resolved_session_id} already finalized (no explicit transcript), skipping"
                    )
                    return _finish(True, "completed")
                logger.info(
                    f"Session {resolved_session_id} already ingested; retrying pending sync"
                )
                skip_ingest = True

        if not skip_ingest:
            # 3. Ingest tracker issue metadata if available
            tracker_state = _find_tracker_state(resolved_session_id)
            issue_meta = {}
            if tracker_state is None:
                print("[cloudmem] No external tracker state found — skipping issue metadata")
            else:
                issue_meta = {
                    "session_id": resolved_session_id,
                    "issue_repo": tracker_state.get("notesRepo") or None,
                    "issue_number": tracker_state.get("issueNumber") or None,
                    "issue_url": tracker_state.get("issueUrl") or None,
                }
                if issue_meta.get("issue_number") and issue_meta.get("issue_url"):
                    manifest.set_issue(
                        repo=issue_meta["issue_repo"] or "",
                        number=issue_meta["issue_number"],
                        url=issue_meta["issue_url"],
                    )

            # 4. Ingest transcript
            cwd = hook_data.get("cwd") or os.getcwd()
            wing = Path(cwd).name.lower().replace(" ", "_").replace("-", "_")

            if transcript_explicit:
                if not resolved_transcript or not Path(resolved_transcript).is_file():
                    logger.error(f"Transcript file not found: {resolved_transcript!r}")
                    manifest.set_ingest_failed(
                        "transcript_not_found",
                        transcript_path=resolved_transcript or str(transcript_input or ""),
                    )
                    return _finish(
                        False,
                        "failed",
                        error_code="transcript_not_found",
                        error_detail="Transcript file not found",
                    )

                try:
                    from .convo_miner import mine_convo_file

                    result = mine_convo_file(
                        filepath=resolved_transcript,
                        palace_path=self._palace_path,
                        wing=wing,
                        agent="cloudmem",
                        metadata_overrides=issue_meta or None,
                        quiet=True,
                    )
                    manifest.set_ingest(
                        drawers_added=result.get("drawers_added", 0),
                        wing=wing,
                        room=result.get("room"),
                        transcript_sha256=_sha256(resolved_transcript),
                        transcript_path=resolved_transcript,
                        ingested_at=datetime.now(timezone.utc).isoformat(),
                    )
                except Exception as e:
                    logger.error(f"Ingest failed: {e}")
                    manifest.set_ingest_failed(
                        "ingest_exception",
                        detail=str(e),
                        transcript_path=resolved_transcript,
                    )
                    return _finish(
                        False,
                        "failed",
                        error_code="ingest_exception",
                        error_detail=str(e),
                    )
            else:
                # No explicit transcript path — ingest latest Claude project dir only if valid.
                claude_projects = os.environ.get(
                    "CLOUDMEM_CLAUDE_PROJECTS",
                    os.path.expanduser("~/.claude/projects"),
                )
                projects_root = Path(claude_projects).expanduser()
                if not projects_root.is_dir():
                    manifest.set_ingest_failed(
                        "no_transcript_source",
                        claude_projects_path=str(projects_root),
                    )
                    return _finish(
                        False,
                        "failed",
                        error_code="no_transcript_source",
                        error_detail="No fallback transcript source",
                    )

                latest_dirs = sorted(
                    [p for p in projects_root.iterdir() if p.is_dir()],
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if not latest_dirs:
                    manifest.set_ingest_failed(
                        "no_transcript_source",
                        claude_projects_path=str(projects_root),
                        reason="no_project_dirs",
                    )
                    return _finish(
                        False,
                        "failed",
                        error_code="no_transcript_source",
                        error_detail="No fallback transcript source",
                    )

                latest_dir = latest_dirs[0]
                try:
                    from .convo_miner import mine_convos, scan_convos

                    convo_files = scan_convos(str(latest_dir))
                    if not convo_files:
                        manifest.set_ingest_failed(
                            "fallback_no_conversations",
                            source_dir=str(latest_dir),
                        )
                        return _finish(
                            False,
                            "failed",
                            error_code="fallback_no_conversations",
                            error_detail="No conversations in fallback source",
                        )

                    mine_convos(
                        convo_dir=str(latest_dir),
                        palace_path=self._palace_path,
                        wing=wing,
                        agent="cloudmem",
                        quiet=True,
                    )
                    manifest.set_ingest(
                        source="latest_project_dir",
                        source_dir=str(latest_dir),
                        files_found=len(convo_files),
                        wing=wing,
                        ingested_at=datetime.now(timezone.utc).isoformat(),
                    )
                except Exception as e:
                    logger.error(f"Fallback ingest failed: {e}")
                    manifest.set_ingest_failed(
                        "ingest_exception",
                        detail=str(e),
                        source_dir=str(latest_dir),
                    )
                    return _finish(
                        False,
                        "failed",
                        error_code="ingest_exception",
                        error_detail=str(e),
                    )

        # 5. Push to GitHub
        try:
            from .sync import SyncManager

            mgr = SyncManager(repo_root=self._repo_root)
            if mgr.is_git_repo() and mgr._get_remote_url():
                result = mgr.push(f"cloudmem: session {resolved_session_id[:8]}")
                if result.ok:
                    manifest.set_sync(
                        commit_sha=result.data.get("commit_sha", ""),
                        pushed_at=datetime.now(timezone.utc).isoformat(),
                    )
                else:
                    manifest.set_sync_pending(result.data.get("error", "push_failed"))
        except Exception as e:
            manifest.set_sync_pending(str(e))

        return _finish(True, "completed")
