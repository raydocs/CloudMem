# Core coverage: init config generation behavior (empty/non-empty/existing/overwrite) for mempalace.yaml.

import yaml

from cloudmem.project_init import bootstrap_project_config


def test_empty_project_generates_general_room_only(tmp_project):
    empty_project = tmp_project.parent / "empty_project"
    empty_project.mkdir()

    config_path = bootstrap_project_config(empty_project)
    config = yaml.safe_load(config_path.read_text())

    assert config_path.name == "mempalace.yaml"
    assert [room["name"] for room in config["rooms"]] == ["general"]


def test_project_with_src_docs_tests_generates_3_plus_general_rooms(tmp_project):
    config_path = bootstrap_project_config(tmp_project)
    config = yaml.safe_load(config_path.read_text())
    room_names = [room["name"] for room in config["rooms"]]

    assert "src" in room_names
    assert "docs" in room_names
    assert "tests" in room_names
    assert "general" in room_names
    assert len(room_names) >= 4


def test_existing_mempalace_yaml_is_not_overwritten(tmp_project):
    config_path = tmp_project / "mempalace.yaml"
    original = "wing: keep\nrooms:\n  - name: legacy\n"
    config_path.write_text(original)

    returned = bootstrap_project_config(tmp_project)

    assert returned == config_path
    assert config_path.read_text() == original


def test_overwrite_true_rebuilds_existing_config(tmp_project):
    config_path = tmp_project / "mempalace.yaml"
    config_path.write_text("wing: old\nrooms:\n  - name: legacy\n")

    returned = bootstrap_project_config(tmp_project, overwrite=True)
    config = yaml.safe_load(returned.read_text())
    room_names = [room["name"] for room in config["rooms"]]

    assert returned == config_path
    assert "legacy" not in room_names
    assert "general" in room_names
