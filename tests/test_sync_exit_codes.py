# Core assertion: sync CLI commands must return non-zero exit codes on failure.

import os
import subprocess
import sys
from pathlib import Path


def _run_cloudmem(args, cwd: Path, cloudmem_home: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    env["CLOUDMEM_HOME"] = str(cloudmem_home)
    env["CLOUDMEM_PALACE_PATH"] = str(cloudmem_home / "palace")
    return subprocess.run(
        [sys.executable, "-m", "cloudmem", *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )


def test_push_returns_nonzero_outside_git_repo(tmp_path):
    cloudmem_home = tmp_path / ".cloudmem"
    cloudmem_home.mkdir()

    workdir = tmp_path / "not_a_repo"
    workdir.mkdir()

    result = _run_cloudmem(["push"], cwd=workdir, cloudmem_home=cloudmem_home)

    assert result.returncode != 0


def test_clone_returns_nonzero_for_invalid_url(tmp_path):
    cloudmem_home = tmp_path / ".cloudmem"
    cloudmem_home.mkdir()

    result = _run_cloudmem(
        ["clone", "not-a-valid-git-url"],
        cwd=tmp_path,
        cloudmem_home=cloudmem_home,
    )

    assert result.returncode != 0


def test_ensure_gitignore_appends_required_rules(tmp_path):
    from cloudmem.sync import SyncManager

    repo_root = tmp_path / ".cloudmem"
    repo_root.mkdir()
    gitignore = repo_root / ".gitignore"
    gitignore.write_text("custom-rule\n")

    mgr = SyncManager(repo_root=str(repo_root))
    mgr._ensure_gitignore()

    content = gitignore.read_text()
    assert "custom-rule" in content
    assert "palace/" in content
    assert ".sync.lock" in content
