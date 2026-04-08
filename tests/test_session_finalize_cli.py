# Core assertion: session-finalize CLI must return non-zero when finalization fails.

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


def test_session_finalize_returns_nonzero_when_transcript_missing(tmp_path):
    cloudmem_home = tmp_path / ".cloudmem"
    cloudmem_home.mkdir()

    missing = tmp_path / "missing-transcript.md"

    result = _run_cloudmem(
        [
            "session-finalize",
            "--session-id",
            "sess-cli-missing",
            "--transcript",
            str(missing),
        ],
        cwd=tmp_path,
        cloudmem_home=cloudmem_home,
    )

    assert result.returncode != 0
