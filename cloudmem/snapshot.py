"""Portable snapshot helpers for syncing CloudMem without shipping live Chroma files."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from .storage import get_chroma_client, get_collection_name, get_drawer_collection

SNAPSHOT_FILENAME = "palace_export.json"
SNAPSHOT_VERSION = 1


def _read_all_drawers(collection, where: dict | None = None, batch_size: int = 1000) -> list[dict]:
    drawers = []
    offset = 0

    while True:
        kwargs = {
            "include": ["documents", "metadatas"],
            "limit": batch_size,
            "offset": offset,
        }
        if where:
            kwargs["where"] = where

        results = collection.get(**kwargs)
        ids = results.get("ids", [])
        if not ids:
            break

        for drawer_id, doc, meta in zip(ids, results.get("documents", []), results.get("metadatas", [])):
            drawers.append({"id": drawer_id, "content": doc, "metadata": meta})

        offset += len(ids)

    return drawers


def export_snapshot(
    snapshot_path: str | Path,
    palace_path: str | Path | None = None,
    *,
    collection_name: str | None = None,
    wing: str | None = None,
) -> dict:
    snapshot_path = Path(snapshot_path).expanduser().resolve()
    collection_name = get_collection_name(collection_name)
    palace_dir = Path(palace_path).expanduser().resolve() if palace_path else None

    if palace_dir is not None and not palace_dir.exists():
        drawers = []
    else:
        collection = get_drawer_collection(
            palace_path=palace_dir,
            collection_name=collection_name,
            create=False,
        )
        where = {"wing": wing} if wing else None
        drawers = _read_all_drawers(collection, where=where)

    snapshot = {
        "version": SNAPSHOT_VERSION,
        "exported_at": datetime.now().isoformat(),
        "collection_name": collection_name,
        "wing_filter": wing,
        "count": len(drawers),
        "drawers": drawers,
    }

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(snapshot, indent=2))
    return snapshot


def import_snapshot(
    snapshot_path: str | Path,
    palace_path: str | Path | None = None,
    *,
    replace: bool = False,
) -> dict:
    snapshot_path = Path(snapshot_path).expanduser().resolve()
    snapshot = json.loads(snapshot_path.read_text())
    drawers = snapshot.get("drawers", [])

    palace_dir = Path(palace_path).expanduser().resolve() if palace_path else None
    if palace_dir and replace and palace_dir.exists():
        shutil.rmtree(palace_dir)

    client = get_chroma_client(palace_dir)
    collection_name = get_collection_name(snapshot.get("collection_name"))
    collection = client.get_or_create_collection(collection_name)

    imported = 0
    skipped = 0
    for drawer in drawers:
        try:
            collection.add(
                ids=[drawer["id"]],
                documents=[drawer["content"]],
                metadatas=[drawer["metadata"]],
            )
            imported += 1
        except Exception as e:
            if "already exists" in str(e).lower():
                skipped += 1
            else:
                raise

    return {
        "version": snapshot.get("version", SNAPSHOT_VERSION),
        "collection_name": collection_name,
        "count": len(drawers),
        "imported": imported,
        "skipped": skipped,
    }
