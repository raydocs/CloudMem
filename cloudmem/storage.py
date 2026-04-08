"""Shared Chroma client and collection access for CloudMem."""
from collections.abc import Iterator
from pathlib import Path

import chromadb
from chromadb.config import Settings

from cloudmem.config import MempalaceConfig
from cloudmem.paths import get_palace_path

_DEFAULT_COLLECTION = "mempalace_drawers"
DEFAULT_READ_BATCH_SIZE = 1000


def get_collection_name(collection_name: str | None = None) -> str:
    if collection_name:
        return collection_name
    return MempalaceConfig().collection_name or _DEFAULT_COLLECTION


def get_chroma_settings(palace_path: Path | None = None) -> Settings:
    path = palace_path or get_palace_path()
    return Settings(
        is_persistent=True,
        persist_directory=str(path),
        anonymized_telemetry=False,
    )


def get_chroma_client(palace_path: Path | None = None) -> chromadb.PersistentClient:
    path = palace_path or get_palace_path()
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path), settings=get_chroma_settings(path))


def get_drawer_collection(
    palace_path: Path | None = None,
    collection_name: str | None = None,
    *,
    create: bool = True,
) -> chromadb.Collection:
    client = get_chroma_client(palace_path)
    name = get_collection_name(collection_name)
    if create:
        return client.get_or_create_collection(name)
    return client.get_collection(name)


def iter_collection_rows(
    collection,
    *,
    include: list[str] | None = None,
    where: dict | None = None,
    batch_size: int = DEFAULT_READ_BATCH_SIZE,
) -> Iterator[dict]:
    """Yield collection rows in batches so callers avoid full-collection reads."""
    requested = tuple(include or ())
    offset = 0

    while True:
        kwargs = {"limit": batch_size, "offset": offset}
        if include:
            kwargs["include"] = include
        if where:
            kwargs["where"] = where

        response = collection.get(**kwargs)
        ids = response.get("ids", [])
        if not ids:
            break

        documents = response.get("documents", [])
        metadatas = response.get("metadatas", [])
        distances = response.get("distances", [])

        for index, drawer_id in enumerate(ids):
            row = {"id": drawer_id}
            if "documents" in requested:
                row["document"] = documents[index] if index < len(documents) else None
            if "metadatas" in requested:
                row["metadata"] = metadatas[index] if index < len(metadatas) else None
            if "distances" in requested:
                row["distance"] = distances[index] if index < len(distances) else None
            yield row

        offset += len(ids)
        if len(ids) < batch_size:
            break
