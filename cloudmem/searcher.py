#!/usr/bin/env python3
"""
searcher.py — Find anything. Exact words.

Semantic search against the palace.
Returns verbatim text — the actual words, never summaries.
"""

import re
import sys
from pathlib import Path

from .storage import get_drawer_collection

_TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]+")
# Merge same-file hits when chunk indices are near each other,
# even if there's a small gap (e.g., 0 and 2).
NEARBY_CHUNK_WINDOW = 2


def _normalize_terms(query: str) -> list[str]:
    terms = []
    seen = set()
    for raw in _TOKEN_RE.findall(query.lower()):
        token = raw.strip("._/-:")
        if len(token) < 2 or token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return terms


def _source_display(source_file: str | None) -> str:
    if not source_file:
        return "?"
    source = str(source_file)
    path = Path(source)
    if path.is_absolute():
        return path.name
    return source


def _semantic_score(distance) -> float:
    if distance is None:
        return 0.0
    try:
        value = float(distance)
    except (TypeError, ValueError):
        return 0.0
    if value < 0:
        value = 0.0
    return round(1.0 / (1.0 + value), 3)


def _chunk_index(metadata: dict) -> int | None:
    value = (metadata or {}).get("chunk_index")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _rerank_hits(query: str, docs: list, metas: list, dists: list) -> list[dict]:
    query_lower = query.lower().strip()
    terms = _normalize_terms(query)
    hits = []

    for doc, meta, dist in zip(docs, metas, dists):
        text = doc or ""
        metadata = meta or {}
        source_file = metadata.get("source_file", "")
        source_display = _source_display(source_file)
        source_lower = str(source_file).lower()
        room = metadata.get("room", "unknown")
        wing = metadata.get("wing", "unknown")
        room_lower = room.lower()
        wing_lower = wing.lower()
        text_lower = text.lower()

        text_hits = sum(1 for token in terms if token in text_lower)
        source_hits = sum(1 for token in terms if token in source_lower)
        scope_hits = sum(1 for token in terms if token in room_lower or token in wing_lower)
        phrase_in_text = 1 if query_lower and query_lower in text_lower else 0
        phrase_in_source = 1 if query_lower and query_lower in source_lower else 0

        semantic = _semantic_score(dist)
        score = round(
            semantic
            + text_hits * 0.45
            + source_hits * 0.8
            + scope_hits * 0.35
            + phrase_in_text * 1.2
            + phrase_in_source * 1.5,
            3,
        )

        hits.append(
            {
                "text": text,
                "wing": wing,
                "room": room,
                "source_file": source_file,
                "source_name": source_display,
                "distance": None if dist is None else round(float(dist), 3),
                "semantic_score": semantic,
                "similarity": semantic,
                "score": score,
                "keyword_hits": text_hits + source_hits + scope_hits,
                "chunk_index": _chunk_index(metadata),
                "merged_chunks": 1,
                "metadata": metadata,
            }
        )

    hits.sort(
        key=lambda hit: (
            -hit["score"],
            -hit["keyword_hits"],
            -(1 if "/" in hit["source_name"] else 0),
            hit["distance"] if hit["distance"] is not None else float("inf"),
        )
    )
    return hits


def _merge_adjacent_hits(hits: list[dict], n_results: int) -> list[dict]:
    groups: list[dict] = []

    for rank, hit in enumerate(hits):
        chunk_index = hit.get("chunk_index")
        merged = False
        if chunk_index is not None:
            for group in groups:
                same_source = (
                    group["source_file"] == hit["source_file"]
                    and group["wing"] == hit["wing"]
                    and group["room"] == hit["room"]
                )
                nearby = (
                    group["min_chunk"] - NEARBY_CHUNK_WINDOW
                    <= chunk_index
                    <= group["max_chunk"] + NEARBY_CHUNK_WINDOW
                )
                if same_source and nearby:
                    group["hits"].append(hit)
                    group["min_chunk"] = min(group["min_chunk"], chunk_index)
                    group["max_chunk"] = max(group["max_chunk"], chunk_index)
                    merged = True
                    break

        if not merged:
            groups.append(
                {
                    "hits": [hit],
                    "source_file": hit["source_file"],
                    "wing": hit["wing"],
                    "room": hit["room"],
                    "min_chunk": chunk_index if chunk_index is not None else rank,
                    "max_chunk": chunk_index if chunk_index is not None else rank,
                }
            )

    merged_hits = []
    for group in groups:
        ordered = sorted(
            group["hits"],
            key=lambda hit: (
                hit.get("chunk_index") is None,
                hit.get("chunk_index") if hit.get("chunk_index") is not None else 0,
            ),
        )
        best = max(
            ordered,
            key=lambda hit: (
                hit["score"],
                hit["keyword_hits"],
                -(hit["distance"] if hit["distance"] is not None else float("inf")),
            ),
        )

        texts = []
        seen = set()
        for item in ordered:
            text = item["text"].strip()
            if text and text not in seen:
                seen.add(text)
                texts.append(text)

        merged_hit = dict(best)
        merged_hit["text"] = "\n\n".join(texts)
        merged_hit["merged_chunks"] = len(ordered)
        if len(ordered) > 1:
            merged_hit["chunk_range"] = [group["min_chunk"], group["max_chunk"]]
        merged_hits.append(merged_hit)

    merged_hits.sort(
        key=lambda hit: (
            -hit["score"],
            -hit["keyword_hits"],
            -hit.get("merged_chunks", 1),
            hit["distance"] if hit["distance"] is not None else float("inf"),
        )
    )
    return merged_hits[:n_results]


def _query_collection(col, query: str, where: dict, n_results: int) -> list[dict]:
    candidate_count = max(n_results * 6, n_results, 12)
    kwargs = {
        "query_texts": [query],
        "n_results": candidate_count,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    results = col.query(**kwargs)

    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]
    hits = _rerank_hits(query, docs, metas, dists)
    return _merge_adjacent_hits(hits, n_results=n_results)


def search(query: str, palace_path: str, wing: str = None, room: str = None, n_results: int = 5):
    """
    Search the palace. Returns verbatim drawer content.
    Optionally filter by wing (project) or room (aspect).
    """
    try:
        col = get_drawer_collection(palace_path=Path(palace_path), create=False)
    except Exception:
        print(f"\n  No palace found at {palace_path}")
        print("  Run: mempalace init <dir> then mempalace mine <dir>")
        sys.exit(1)

    # Build where filter
    where = {}
    if wing and room:
        where = {"$and": [{"wing": wing}, {"room": room}]}
    elif wing:
        where = {"wing": wing}
    elif room:
        where = {"room": room}

    try:
        hits = _query_collection(col, query=query, where=where, n_results=n_results)
    except Exception as e:
        print(f"\n  Search error: {e}")
        sys.exit(1)

    if not hits:
        print(f'\n  No results found for: "{query}"')
        return

    print(f"\n{'=' * 60}")
    print(f'  Results for: "{query}"')
    if wing:
        print(f"  Wing: {wing}")
    if room:
        print(f"  Room: {room}")
    print(f"{'=' * 60}\n")

    for i, hit in enumerate(hits, 1):
        doc = hit["text"]
        wing_name = hit["wing"]
        room_name = hit["room"]

        print(f"  [{i}] {wing_name} / {room_name}")
        print(f"      Source: {hit['source_name']}")
        if hit.get("chunk_range"):
            print(f"      Chunks: {hit['chunk_range'][0]}-{hit['chunk_range'][1]}")
        print(f"      Score:  {hit['score']}")
        if hit["distance"] is not None:
            print(f"      Dist:   {hit['distance']}")
        print()
        # Print the verbatim text, indented
        for line in doc.strip().split("\n"):
            print(f"      {line}")
        print()
        print(f"  {'─' * 56}")

    print()


def search_memories(
    query: str, palace_path: str, wing: str = None, room: str = None, n_results: int = 5
) -> dict:
    """
    Programmatic search — returns a dict instead of printing.
    Used by the MCP server and other callers that need data.
    """
    try:
        col = get_drawer_collection(palace_path=Path(palace_path), create=False)
    except Exception as e:
        return {"error": f"No palace found at {palace_path}: {e}"}

    # Build where filter
    where = {}
    if wing and room:
        where = {"$and": [{"wing": wing}, {"room": room}]}
    elif wing:
        where = {"wing": wing}
    elif room:
        where = {"room": room}

    try:
        hits = _query_collection(col, query=query, where=where, n_results=n_results)
    except Exception as e:
        return {"error": f"Search error: {e}"}

    return {
        "query": query,
        "filters": {"wing": wing, "room": room},
        "results": hits,
    }
