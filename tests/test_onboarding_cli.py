# Core coverage: CLI help exposes onboard command and command registration does not raise ImportError.

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


def _run_cloudmem_cli(*args):
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    return subprocess.run(
        [sys.executable, "-m", "cloudmem", *args],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
    )


def test_main_help_contains_onboard_command():
    result = _run_cloudmem_cli("--help")

    assert result.returncode == 0
    assert "onboard" in result.stdout


def test_onboard_subcommand_help_smoke_no_import_error():
    result = _run_cloudmem_cli("onboard", "--help")

    assert result.returncode == 0
    assert "ImportError" not in result.stderr
    assert "--directory" in result.stdout
    assert "--no-auto-detect" in result.stdout


def test_cmd_onboard_passes_cli_arguments(monkeypatch, tmp_path):
    from cloudmem import cli, onboarding

    called = {}

    def _fake_run_onboarding(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(onboarding, "run_onboarding", _fake_run_onboarding)

    cli.cmd_onboard(
        SimpleNamespace(
            directory="/tmp/demo",
            config_dir=str(tmp_path),
            no_auto_detect=True,
        )
    )

    assert called["directory"] == "/tmp/demo"
    assert called["config_dir"] == tmp_path.resolve()
    assert called["auto_detect"] is False
