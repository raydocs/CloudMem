# Smoke-to-test regressions:
# - Layer1.generate should produce meaningful output from weighted drawers.
# - Graph metadata pagination should aggregate across multiple collection.get pages.

from __future__ import annotations

from cloudmem.layers import Layer1
from cloudmem.palace_graph import build_graph


class _PagedCollection:
    def __init__(self, metadatas: list[dict]):
        self._metadatas = metadatas

    def count(self):
        return len(self._metadatas)

    def get(self, limit=1000, offset=0, include=None):
        batch = self._metadatas[offset : offset + limit]
        ids = [f"id-{i}" for i in range(offset, offset + len(batch))]
        return {"ids": ids, "metadatas": batch}


def test_layer1_generate_builds_compact_story(monkeypatch, tmp_path):
    # Arrange
    rows = [
        {
            "document": "Implemented rollback safety in the transaction manager.",
            "metadata": {
                "room": "backend",
                "source_file": "src/txn.py",
                "importance": 5,
                "filed_at": "2026-04-07T10:00:00",
            },
        },
        {
            "document": "Documented release checklist and RC gate decisions.",
            "metadata": {
                "room": "ops",
                "source_file": "docs/release.md",
                "importance": 4,
                "filed_at": "2026-04-07T09:00:00",
            },
        },
    ]

    monkeypatch.setattr("cloudmem.layers.get_drawer_collection", lambda *args, **kwargs: object())
    monkeypatch.setattr("cloudmem.layers.iter_collection_rows", lambda *args, **kwargs: iter(rows))

    # Act
    text = Layer1(palace_path=str(tmp_path / "palace")).generate()

    # Assert
    assert "## L1 — ESSENTIAL STORY" in text
    assert "[backend]" in text
    assert "[ops]" in text
    assert "rollback safety" in text
    assert "release checklist" in text


def test_build_graph_aggregates_metadata_across_pages():
    # This guards the pagination aggregation used by graph/MCP traversal flows.
    col = _PagedCollection(
        [
            {"wing": "wing_code", "room": "auth", "hall": "hall_facts", "date": "2026-04-01"},
            {"wing": "wing_ops", "room": "auth", "hall": "hall_events", "date": "2026-04-02"},
            {"wing": "wing_code", "room": "billing", "hall": "hall_facts", "date": "2026-04-03"},
        ]
    )

    nodes, edges = build_graph(col=col)

    assert "auth" in nodes
    assert sorted(nodes["auth"]["wings"]) == ["wing_code", "wing_ops"]
    assert nodes["auth"]["count"] == 2
    assert any(edge["room"] == "auth" for edge in edges)
