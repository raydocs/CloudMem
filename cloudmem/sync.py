"""
CloudMem SyncManager — push/pull the entire CloudMem storage root to/from GitHub.

Repo root: ~/.cloudmem  (not just the palace subdir)
ChromaDB binary files are excluded via .gitignore — only text/SQLite assets sync.
"""

import os
import subprocess
from pathlib import Path
from datetime import datetime

from .config import get_cloudmem_home, get_palace_path


GITIGNORE_CONTENT = """\
# ChromaDB vector store — binary, non-portable, rebuilt on import
chroma*/
*.chroma/

# Runtime / temp
*.log
*.tmp
*.lock
__pycache__/
*.pyc
cache/
logs/

# Machine-local config
local.json
"""


class SyncResult:
    def __init__(self, ok: bool, operation: str, **kwargs):
        self.ok = ok
        self.operation = operation
        self.data = kwargs

    def to_dict(self) -> dict:
        return {"ok": self.ok, "operation": self.operation, **self.data}

    def __repr__(self):
        return f"SyncResult(ok={self.ok}, op={self.operation}, data={self.data})"


class SyncManager:
    """Manages git-based sync of the CloudMem storage root to a remote GitHub repo."""

    def __init__(self, repo_root: str = None):
        self._repo_root = Path(repo_root or get_cloudmem_home()).expanduser().resolve()

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    @property
    def lock_file(self) -> Path:
        return self._repo_root / ".sync.lock"

    def _run(self, cmd: list[str], silent: bool = False) -> tuple[int, str]:
        result = subprocess.run(
            cmd,
            cwd=self._repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.returncode, (result.stdout + result.stderr).strip()

    def is_git_repo(self) -> bool:
        return (self._repo_root / ".git").is_dir()

    def _ensure_gitignore(self):
        gi = self._repo_root / ".gitignore"
        if not gi.exists():
            gi.write_text(GITIGNORE_CONTENT)

    def _get_remote_url(self) -> str | None:
        code, out = self._run(["git", "remote", "get-url", "origin"])
        return out.strip() if code == 0 else None

    def status(self) -> SyncResult:
        if not self.is_git_repo():
            return SyncResult(False, "status", error="not_a_git_repo",
                              hint="Run: cloudmem sync-init <github-url>")
        code, dirty = self._run(["git", "status", "--porcelain"])
        remote = self._get_remote_url()
        _, branch_out = self._run(["git", "branch", "--show-current"])
        return SyncResult(True, "status",
                          repo_root=str(self._repo_root),
                          remote_url=remote,
                          branch=branch_out.strip(),
                          dirty=bool(dirty.strip()),
                          sync_enabled=remote is not None)

    def init_sync(self, remote_url: str, branch: str = "main") -> SyncResult:
        """One-time setup: init repo and link remote."""
        self._repo_root.mkdir(parents=True, exist_ok=True)

        if not self.is_git_repo():
            self._run(["git", "init"])
            self._run(["git", "branch", "-m", branch])

        self._ensure_gitignore()

        _, remotes = self._run(["git", "remote"])
        if "origin" in remotes:
            self._run(["git", "remote", "set-url", "origin", remote_url])
        else:
            self._run(["git", "remote", "add", "origin", remote_url])

        return SyncResult(True, "sync-init",
                          repo_root=str(self._repo_root),
                          remote_url=remote_url,
                          branch=branch)

    def push(self, message: str = None) -> SyncResult:
        """Commit all changes and push to GitHub."""
        if not self.is_git_repo():
            return SyncResult(False, "push", error="not_a_git_repo")

        remote = self._get_remote_url()
        if not remote:
            return SyncResult(False, "push", error="no_remote_configured",
                              hint="Run: cloudmem sync-init <github-url>")

        self._run(["git", "add", "-A"])

        code, dirty = self._run(["git", "status", "--porcelain"])
        if not dirty.strip():
            return SyncResult(True, "push", changed=False, message="nothing to commit")

        commit_msg = message or f"cloudmem: auto-sync {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        code, out = self._run(["git", "commit", "-m", commit_msg, "--quiet"])
        if code != 0:
            return SyncResult(False, "push", error="commit_failed", detail=out)

        _, branch_out = self._run(["git", "branch", "--show-current"])
        branch = branch_out.strip() or "main"
        code, out = self._run(["git", "push", "-u", "origin", branch, "--quiet"])
        if code != 0:
            return SyncResult(False, "push", error="push_failed", detail=out)

        _, sha_out = self._run(["git", "rev-parse", "HEAD"])
        return SyncResult(True, "push", changed=True,
                          commit_sha=sha_out.strip(), remote_url=remote)

    def pull(self) -> SyncResult:
        """Pull latest from GitHub. Refuses if working tree is dirty."""
        if not self.is_git_repo():
            return SyncResult(False, "pull", error="not_a_git_repo")

        code, dirty = self._run(["git", "status", "--porcelain"])
        if dirty.strip():
            return SyncResult(False, "pull", error="dirty_worktree",
                              hint="Commit or stash local changes before pulling")

        code, out = self._run(["git", "pull", "--rebase", "origin"])
        if code != 0:
            return SyncResult(False, "pull", error="pull_failed", detail=out)

        return SyncResult(True, "pull", detail=out)

    def clone(self, remote_url: str) -> SyncResult:
        """Bootstrap on a new machine: clone from GitHub into repo_root."""
        if self._repo_root.exists() and any(self._repo_root.iterdir()):
            return SyncResult(False, "clone", error="target_not_empty",
                              path=str(self._repo_root))

        self._repo_root.parent.mkdir(parents=True, exist_ok=True)
        code, out = subprocess.run(
            ["git", "clone", remote_url, str(self._repo_root)],
            capture_output=True, text=True
        ).returncode, ""

        if code != 0:
            return SyncResult(False, "clone", error="clone_failed", detail=out)

        return SyncResult(True, "clone", remote_url=remote_url,
                          repo_root=str(self._repo_root))
