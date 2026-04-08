import pytest, tempfile, os
from pathlib import Path


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    """Redirect ~/.cloudmem and ~/.mempalace to tmp_path for isolation."""
    cloudmem_home = tmp_path / ".cloudmem"
    cloudmem_home.mkdir()
    monkeypatch.setenv("CLOUDMEM_HOME", str(cloudmem_home))
    monkeypatch.setenv("CLOUDMEM_PALACE_PATH", str(cloudmem_home / "palace"))
    return tmp_path


@pytest.fixture
def tmp_project(tmp_path):
    """A temporary project directory."""
    proj = tmp_path / "my_project"
    proj.mkdir()
    (proj / "src").mkdir()
    (proj / "docs").mkdir()
    (proj / "tests").mkdir()
    return proj
