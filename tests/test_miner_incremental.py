import importlib
import subprocess
import sys
import types


class FakeCollection:
    def __init__(self):
        self.records = {}

    def get(self, where=None, include=None, limit=None, offset=0):
        items = list(self.records.items())
        if where and "source_file" in where:
            items = [item for item in items if item[1]["metadata"].get("source_file") == where["source_file"]]
        if offset:
            items = items[offset:]
        if limit is not None:
            items = items[:limit]
        return {
            "ids": [drawer_id for drawer_id, _ in items],
            "documents": [record["document"] for _, record in items],
            "metadatas": [record["metadata"] for _, record in items],
        }

    def add(self, documents, ids, metadatas):
        for doc, drawer_id, meta in zip(documents, ids, metadatas):
            self.records[drawer_id] = {"document": doc, "metadata": meta}

    def delete(self, ids):
        for drawer_id in ids:
            self.records.pop(drawer_id, None)


def _import_miner_with_fake_chromadb(monkeypatch):
    chromadb_mod = types.ModuleType("chromadb")
    chromadb_mod.PersistentClient = object
    chromadb_mod.Collection = object

    chromadb_config_mod = types.ModuleType("chromadb.config")

    class Settings:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    chromadb_config_mod.Settings = Settings

    monkeypatch.setitem(sys.modules, "chromadb", chromadb_mod)
    monkeypatch.setitem(sys.modules, "chromadb.config", chromadb_config_mod)

    import cloudmem.storage as storage
    import cloudmem.miner as miner

    importlib.reload(storage)
    return importlib.reload(miner)


def test_process_file_uses_relative_paths_and_hashes(monkeypatch, tmp_path):
    miner = _import_miner_with_fake_chromadb(monkeypatch)

    project_path = tmp_path / "project"
    project_path.mkdir()
    filepath = project_path / "src.py"
    filepath.write_text(
        "def demo():\n"
        "    note = 'this file is intentionally long enough for chunking checks'\n"
        "    return note\n"
    )

    collection = FakeCollection()
    rooms = [{"name": "general", "description": "All files", "keywords": []}]

    result = miner.process_file(
        filepath=filepath,
        project_path=project_path,
        collection=collection,
        wing="project",
        rooms=rooms,
        agent="test",
        dry_run=False,
    )

    assert result["status"] == "processed"
    assert result["drawers_added"] > 0

    record = next(iter(collection.records.values()))
    assert record["metadata"]["source_file"] == "src.py"
    assert record["metadata"]["content_sha256"]
    assert record["metadata"]["ingest_mode"] == miner.PROJECT_INGEST_MODE


def test_process_file_rebuilds_when_content_changes(monkeypatch, tmp_path):
    miner = _import_miner_with_fake_chromadb(monkeypatch)

    project_path = tmp_path / "project"
    project_path.mkdir()
    filepath = project_path / "src.py"
    filepath.write_text(
        "def demo():\n"
        "    note = 'this file is intentionally long enough for chunking checks'\n"
        "    return note\n"
    )

    collection = FakeCollection()
    rooms = [{"name": "general", "description": "All files", "keywords": []}]

    first = miner.process_file(
        filepath=filepath,
        project_path=project_path,
        collection=collection,
        wing="project",
        rooms=rooms,
        agent="test",
        dry_run=False,
    )
    first_ids = set(collection.records)
    first_hash = next(iter(collection.records.values()))["metadata"]["content_sha256"]

    second = miner.process_file(
        filepath=filepath,
        project_path=project_path,
        collection=collection,
        wing="project",
        rooms=rooms,
        agent="test",
        dry_run=False,
    )
    assert second["status"] == "unchanged"
    assert set(collection.records) == first_ids

    filepath.write_text(
        "def demo():\n"
        "    note = 'this file changed and should produce a fresh content hash'\n"
        "    return note\n"
    )

    third = miner.process_file(
        filepath=filepath,
        project_path=project_path,
        collection=collection,
        wing="project",
        rooms=rooms,
        agent="test",
        dry_run=False,
    )

    assert first["drawers_added"] > 0
    assert third["status"] == "processed"
    assert third["drawers_added"] > 0
    assert set(collection.records) != first_ids
    assert next(iter(collection.records.values()))["metadata"]["content_sha256"] != first_hash


def test_scan_project_respects_gitignore_and_size_limit(monkeypatch, tmp_path):
    miner = _import_miner_with_fake_chromadb(monkeypatch)

    project_path = tmp_path / "project"
    project_path.mkdir()
    subprocess.run(["git", "init"], cwd=project_path, check=True, capture_output=True)

    (project_path / ".gitignore").write_text("ignored.py\nignored_dir/\n")
    (project_path / "app.py").write_text("print('keep me')\n")
    (project_path / "ignored.py").write_text("print('ignore me')\n")
    (project_path / "package-lock.json").write_text("{}\n")
    (project_path / "ignored_dir").mkdir()
    (project_path / "ignored_dir" / "inside.py").write_text("print('hidden')\n")
    (project_path / "huge.md").write_text("x" * 200)

    monkeypatch.setenv("CLOUDMEM_MAX_FILE_BYTES", "64")

    files = miner.scan_project(str(project_path))

    assert [path.name for path in files] == ["app.py"]
