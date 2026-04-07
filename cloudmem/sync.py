"""
CloudMem sync module — push/pull palace to/from GitHub.
Treats ~/.cloudmem/ as a git repo backed by a private GitHub repository.
"""

import os
import subprocess
import sys
from pathlib import Path
from .config import get_palace_path


PALACE_DIR = Path(get_palace_path())


def _run(cmd: list[str], cwd: Path = PALACE_DIR, silent: bool = False) -> int:
    result = subprocess.run(
        cmd, cwd=cwd,
        stdout=subprocess.DEVNULL if silent else None,
        stderr=subprocess.DEVNULL if silent else None,
    )
    return result.returncode


def is_git_repo() -> bool:
    return (PALACE_DIR / ".git").is_dir()


def init_sync(remote_url: str) -> None:
    """One-time setup: init palace dir as git repo and link remote."""
    PALACE_DIR.mkdir(parents=True, exist_ok=True)

    if not is_git_repo():
        _run(["git", "init"])
        _run(["git", "branch", "-m", "main"])

    gitignore = PALACE_DIR / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*.log\n*.tmp\n__pycache__/\n")

    remotes = subprocess.run(
        ["git", "remote"], cwd=PALACE_DIR, capture_output=True, text=True
    ).stdout.strip()

    if "origin" not in remotes:
        _run(["git", "remote", "add", "origin", remote_url])
    else:
        _run(["git", "remote", "set-url", "origin", remote_url])

    print(f"✓ Palace synced to {remote_url}")


def push(message: str = None) -> bool:
    """Commit all palace changes and push to GitHub."""
    if not is_git_repo():
        print("✗ Palace is not a git repo. Run: cloudmem sync-init <github-url>")
        return False

    _run(["git", "add", "-A"])

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=PALACE_DIR, capture_output=True, text=True
    ).stdout.strip()

    if not status:
        return True  # nothing to push

    commit_msg = message or f"palace: auto-sync"
    code = _run(["git", "commit", "-m", commit_msg, "--quiet"])
    if code != 0:
        return False

    code = _run(["git", "push", "-u", "origin", "main", "--quiet"])
    if code != 0:
        print("✗ git push failed — check remote and credentials")
        return False

    return True


def pull() -> bool:
    """Pull latest palace from GitHub (used on a new machine)."""
    if not is_git_repo():
        print("✗ Palace is not a git repo. Run: cloudmem sync-init <github-url>")
        return False

    code = _run(["git", "pull", "--rebase", "origin", "main"])
    if code != 0:
        print("✗ git pull failed")
        return False

    print("✓ Palace updated from GitHub")
    return True


def clone(remote_url: str) -> bool:
    """Bootstrap on a new machine: clone palace from GitHub."""
    parent = PALACE_DIR.parent
    parent.mkdir(parents=True, exist_ok=True)

    if PALACE_DIR.exists() and any(PALACE_DIR.iterdir()):
        print(f"✗ {PALACE_DIR} already exists and is not empty")
        return False

    code = subprocess.run(
        ["git", "clone", remote_url, str(PALACE_DIR)]
    ).returncode

    if code != 0:
        print("✗ git clone failed")
        return False

    print(f"✓ Palace restored from {remote_url}")
    return True
