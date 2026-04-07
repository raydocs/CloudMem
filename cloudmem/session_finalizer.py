"""
SessionFinalizer — Orchestrates post-session work:
1. Read Claude Code hook stdin JSON to identify the session
2. Ingest the session transcript into the palace
3. Write a session manifest (for idempotency + Issue↔drawer linkage)
4. Push palace to GitHub (if sync is configured)
"""

import json
import sys
import os
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone

from .config import get_cloudmem_home, get_palace_path

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

    def set_ingest(self, **kwargs):
        self._data["ingest"] = {"status": "completed", **kwargs}
        self.save()

    def set_ingest_failed(self, error: str):
        self._data["ingest"] = {"status": "failed", "error": error}
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


def _find_tracker_state(session_id: str, hooks_dir: str = None) -> dict:
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
    return {}


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
        resolved_transcript = (
            transcript_path
            or hook_data.get("transcript_path")
            or hook_data.get("transcriptPath")
        )

        manifest = SessionManifest(resolved_session_id, repo_root=self._repo_root)

        # 2. Idempotency: skip if already completed for this transcript
        if manifest.is_complete:
            existing_sha = manifest._data.get("ingest", {}).get("transcript_sha256")
            current_sha = _sha256(resolved_transcript) if resolved_transcript else None
            if existing_sha and existing_sha == current_sha:
                logger.info(f"Session {resolved_session_id} already finalized, skipping")
                return True

        # 3. Ingest tracker issue metadata if available
        tracker_state = _find_tracker_state(resolved_session_id)
        issue_meta = {}
        if tracker_state:
            issue_meta = {
                "session_id": resolved_session_id,
                "issue_repo": tracker_state.get("notesRepo", ""),
                "issue_number": tracker_state.get("issueNumber"),
                "issue_url": tracker_state.get("issueUrl", ""),
            }
            if issue_meta.get("issue_number") and issue_meta.get("issue_url"):
                manifest.set_issue(
                    repo=issue_meta["issue_repo"],
                    number=issue_meta["issue_number"],
                    url=issue_meta["issue_url"],
                )

        # 4. Ingest transcript
        cwd = hook_data.get("cwd") or os.getcwd()
        wing = Path(cwd).name.lower().replace(" ", "_").replace("-", "_")

        if resolved_transcript and Path(resolved_transcript).exists():
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
                manifest.set_ingest_failed(str(e))
                return False
        else:
            # No transcript path — try to ingest latest Claude project dir
            claude_projects = os.environ.get("CLOUDMEM_CLAUDE_PROJECTS",
                                              os.path.expanduser("~/.claude/projects"))
            if os.path.isdir(claude_projects):
                latest = sorted(Path(claude_projects).iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
                if latest:
                    try:
                        from .convo_miner import mine_convos
                        mine_convos(
                            convo_dir=str(latest[0]),
                            palace_path=self._palace_path,
                            wing=wing,
                            agent="cloudmem",
                            quiet=True,
                        )
                        manifest.set_ingest(
                            source="latest_project_dir",
                            wing=wing,
                            ingested_at=datetime.now(timezone.utc).isoformat(),
                        )
                    except Exception as e:
                        logger.error(f"Fallback ingest failed: {e}")
                        manifest.set_ingest_failed(str(e))
                        return False

        # 5. Push to GitHub
        try:
            from .sync import SyncManager
            mgr = SyncManager(repo_root=self._repo_root)
            if mgr.is_git_repo() and mgr._get_remote_url():
                result = mgr.push(f"cloudmem: session {resolved_session_id[:8]}")
                if result.ok:
                    manifest.set_sync(commit_sha=result.data.get("commit_sha", ""),
                                      pushed_at=datetime.now(timezone.utc).isoformat())
                else:
                    manifest.set_sync_pending(result.data.get("error", "push_failed"))
        except Exception as e:
            manifest.set_sync_pending(str(e))

        return True
