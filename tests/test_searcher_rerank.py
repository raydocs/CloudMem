import importlib
import sys
import types


class FakeCollection:
    def __init__(self, results):
        self._results = results

    def query(self, **kwargs):
        return self._results


def _import_searcher_with_fake_chromadb(monkeypatch):
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
    import cloudmem.searcher as searcher

    importlib.reload(storage)
    return importlib.reload(searcher)


def test_search_memories_reranks_using_query_terms_and_paths(monkeypatch, tmp_path):
    searcher = _import_searcher_with_fake_chromadb(monkeypatch)

    fake_results = {
        "documents": [[
            "Generic architecture notes about caching layers and queues.",
            "The auth middleware validates JWT bearer tokens before requests continue.",
            "High-level auth overview in prose.",
        ]],
        "metadatas": [[
            {"wing": "myapp", "room": "architecture", "source_file": "src/cache.py"},
            {"wing": "myapp", "room": "backend", "source_file": "src/auth/middleware.ts"},
            {"wing": "myapp", "room": "docs", "source_file": "docs/auth.md"},
        ]],
        "distances": [[0.04, 0.18, 0.09]],
    }

    monkeypatch.setattr(searcher, "get_drawer_collection", lambda *args, **kwargs: FakeCollection(fake_results))

    payload = searcher.search_memories(
        query="auth middleware jwt",
        palace_path=str(tmp_path / "palace"),
        n_results=3,
    )

    assert payload["results"][0]["source_name"] == "src/auth/middleware.ts"
    assert payload["results"][0]["keyword_hits"] > payload["results"][1]["keyword_hits"]
    assert payload["results"][0]["score"] > payload["results"][1]["score"]


def test_source_name_keeps_relative_paths_and_trims_absolute_paths(monkeypatch, tmp_path):
    searcher = _import_searcher_with_fake_chromadb(monkeypatch)

    fake_results = {
        "documents": [["relative path hit", "absolute path hit"]],
        "metadatas": [[
            {"wing": "myapp", "room": "backend", "source_file": "src/auth/middleware.ts"},
            {"wing": "notes", "room": "general", "source_file": "/tmp/session-export.md"},
        ]],
        "distances": [[0.2, 0.2]],
    }

    monkeypatch.setattr(searcher, "get_drawer_collection", lambda *args, **kwargs: FakeCollection(fake_results))

    payload = searcher.search_memories(
        query="path",
        palace_path=str(tmp_path / "palace"),
        n_results=2,
    )

    names = {hit["source_name"] for hit in payload["results"]}
    assert "src/auth/middleware.ts" in names
    assert "session-export.md" in names


def test_search_memories_merges_adjacent_chunks_from_same_file(monkeypatch, tmp_path):
    searcher = _import_searcher_with_fake_chromadb(monkeypatch)

    fake_results = {
        "documents": [[
            "Transaction setup opens the database connection and begins the unit of work.",
            "Transaction cleanup rolls back on failure and closes the connection safely.",
            "Background worker notes unrelated to the database path.",
        ]],
        "metadatas": [[
            {"wing": "myapp", "room": "backend", "source_file": "src/db/txn.py", "chunk_index": 0},
            {"wing": "myapp", "room": "backend", "source_file": "src/db/txn.py", "chunk_index": 1},
            {"wing": "myapp", "room": "workers", "source_file": "src/workers/jobs.py", "chunk_index": 0},
        ]],
        "distances": [[0.08, 0.1, 0.12]],
    }

    monkeypatch.setattr(searcher, "get_drawer_collection", lambda *args, **kwargs: FakeCollection(fake_results))

    payload = searcher.search_memories(
        query="database transaction rollback",
        palace_path=str(tmp_path / "palace"),
        n_results=2,
    )

    first = payload["results"][0]
    assert first["source_name"] == "src/db/txn.py"
    assert first["merged_chunks"] == 2
    assert first["chunk_range"] == [0, 1]
    assert "Transaction setup opens the database connection" in first["text"]
    assert "Transaction cleanup rolls back on failure" in first["text"]


def test_search_memories_merges_nearby_non_contiguous_chunks(monkeypatch, tmp_path):
    searcher = _import_searcher_with_fake_chromadb(monkeypatch)

    fake_results = {
        "documents": [[
            "Auth setup validates incoming bearer tokens and resolves user context.",
            "Auth errors are translated into typed API responses for clients.",
            "Auth cache warmup keeps token metadata hot in memory.",
            "Far-away chunk from same file that should remain separate.",
        ]],
        "metadatas": [[
            {"wing": "myapp", "room": "backend", "source_file": "src/auth/middleware.ts", "chunk_index": 0},
            {"wing": "myapp", "room": "backend", "source_file": "src/auth/middleware.ts", "chunk_index": 2},
            {"wing": "myapp", "room": "backend", "source_file": "src/auth/middleware.ts", "chunk_index": 1},
            {"wing": "myapp", "room": "backend", "source_file": "src/auth/middleware.ts", "chunk_index": 5},
        ]],
        "distances": [[0.08, 0.09, 0.1, 0.11]],
    }

    monkeypatch.setattr(searcher, "get_drawer_collection", lambda *args, **kwargs: FakeCollection(fake_results))

    payload = searcher.search_memories(
        query="auth token middleware",
        palace_path=str(tmp_path / "palace"),
        n_results=3,
    )

    merged = payload["results"][0]
    assert merged["source_name"] == "src/auth/middleware.ts"
    assert merged["merged_chunks"] == 3
    assert merged["chunk_range"] == [0, 2]
    assert "Auth setup validates incoming bearer tokens" in merged["text"]
    assert "Auth errors are translated into typed API responses" in merged["text"]
    assert "Auth cache warmup keeps token metadata hot" in merged["text"]

    # chunk_index=5 should stay separate because it's outside nearby window.
    assert any(
        r.get("chunk_index") == 5 and r.get("merged_chunks") == 1 for r in payload["results"]
    )
