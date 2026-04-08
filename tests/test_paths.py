# Core coverage: env priority + legacy_fallback migration behavior for path resolution.

from pathlib import Path

from cloudmem import paths


def test_get_cloudmem_home_respects_env(tmp_home, monkeypatch, tmp_path):
    custom_home = tmp_path / "custom-cloudmem-home"
    monkeypatch.setenv("CLOUDMEM_HOME", str(custom_home))

    resolved = paths.get_cloudmem_home()

    assert resolved == custom_home
    assert resolved.exists()


def test_cloudmem_palace_path_env_has_highest_priority(tmp_home, monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUDMEM_HOME", str(tmp_path / "home-a"))
    explicit_palace = tmp_path / "palace-override"
    monkeypatch.setenv("CLOUDMEM_PALACE_PATH", str(explicit_palace))

    assert paths.get_palace_path() == explicit_palace


def test_legacy_fallback_uses_legacy_when_new_missing(tmp_home, monkeypatch, tmp_path):
    legacy_home = tmp_path / ".mempalace"
    legacy_home.mkdir(parents=True)
    legacy_target = legacy_home / "identity.txt"
    legacy_target.write_text("legacy")

    monkeypatch.setattr(paths, "get_legacy_mempalace_home", lambda: legacy_home)

    new_path = tmp_path / ".cloudmem" / "identity.txt"
    resolved = paths.legacy_fallback(new_path, "identity.txt")

    assert resolved == legacy_target


def test_legacy_fallback_prefers_new_path_when_exists(tmp_home, monkeypatch, tmp_path):
    legacy_home = tmp_path / ".mempalace"
    legacy_home.mkdir(parents=True)
    (legacy_home / "identity.txt").write_text("legacy")

    monkeypatch.setattr(paths, "get_legacy_mempalace_home", lambda: legacy_home)

    new_path = tmp_path / ".cloudmem" / "identity.txt"
    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.write_text("new")

    resolved = paths.legacy_fallback(new_path, "identity.txt")

    assert resolved == new_path


def test_write_operations_stay_on_new_cloudmem_path(tmp_home, monkeypatch, tmp_path):
    new_home = tmp_path / ".cloudmem"
    legacy_home = tmp_path / ".mempalace"
    legacy_home.mkdir(parents=True)

    legacy_config = legacy_home / "config.json"
    legacy_config.write_text("legacy-config")

    monkeypatch.setenv("CLOUDMEM_HOME", str(new_home))

    new_config_path = paths.get_config_path()
    new_config_path.write_text("new-config")

    assert new_config_path == new_home / "config.json"
    assert new_config_path.read_text() == "new-config"
    assert legacy_config.read_text() == "legacy-config"
