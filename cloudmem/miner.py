#!/usr/bin/env python3
"""
miner.py — Files everything into the palace.

Reads mempalace.yaml from the project directory to know the wing + rooms.
Routes each file to the right room based on content.
Stores verbatim chunks as drawers. No summaries. Ever.
"""

import os
import sys
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from collections import defaultdict


from cloudmem.storage import get_drawer_collection, iter_collection_rows

PROJECT_INGEST_MODE = "projects"

READABLE_EXTENSIONS = {
    ".txt",
    ".md",
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".css",
    ".java",
    ".go",
    ".rs",
    ".rb",
    ".sh",
    ".csv",
    ".sql",
    ".toml",
}

SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    ".next",
    "coverage",
    ".mempalace",
}

CHUNK_SIZE = 800  # chars per drawer
CHUNK_OVERLAP = 100  # overlap between chunks
MIN_CHUNK_SIZE = 50  # skip tiny chunks
DEFAULT_MAX_FILE_BYTES = 1024 * 1024

SKIP_FILENAMES = {
    "mempalace.yaml",
    "mempalace.yml",
    "mempal.yaml",
    "mempal.yml",
    ".gitignore",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
    "poetry.lock",
    "pdm.lock",
    "Pipfile.lock",
    "Cargo.lock",
}


# =============================================================================
# CONFIG
# =============================================================================


def load_config(project_dir: str) -> dict:
    """Load mempalace.yaml from project directory (falls back to mempal.yaml)."""
    import yaml

    config_path = Path(project_dir).expanduser().resolve() / "mempalace.yaml"
    if not config_path.exists():
        # Fallback to legacy name
        legacy_path = Path(project_dir).expanduser().resolve() / "mempal.yaml"
        if legacy_path.exists():
            config_path = legacy_path
        else:
            print(f"ERROR: No mempalace.yaml found in {project_dir}")
            print(f"Run: mempalace init {project_dir}")
            sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


# =============================================================================
# FILE ROUTING — which room does this file belong to?
# =============================================================================


def detect_room(filepath: Path, content: str, rooms: list, project_path: Path) -> str:
    """
    Route a file to the right room.
    Priority:
    1. Folder path matches a room name
    2. Filename matches a room name or keyword
    3. Content keyword scoring
    4. Fallback: "general"
    """
    relative = str(filepath.relative_to(project_path)).lower()
    filename = filepath.stem.lower()
    content_lower = content[:2000].lower()

    # Priority 1: folder path contains room name
    path_parts = relative.replace("\\", "/").split("/")
    for part in path_parts[:-1]:  # skip filename itself
        for room in rooms:
            if room["name"].lower() in part or part in room["name"].lower():
                return room["name"]

    # Priority 2: filename matches room name
    for room in rooms:
        if room["name"].lower() in filename or filename in room["name"].lower():
            return room["name"]

    # Priority 3: keyword scoring from room keywords + name
    scores = defaultdict(int)
    for room in rooms:
        keywords = room.get("keywords", []) + [room["name"]]
        for kw in keywords:
            count = content_lower.count(kw.lower())
            scores[room["name"]] += count

    if scores:
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best

    return "general"


# =============================================================================
# CHUNKING
# =============================================================================


def chunk_text(content: str, source_file: str) -> list:
    """
    Split content into drawer-sized chunks.
    Tries to split on paragraph/line boundaries.
    Returns list of {"content": str, "chunk_index": int}
    """
    # Clean up
    content = content.strip()
    if not content:
        return []

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(content):
        end = min(start + CHUNK_SIZE, len(content))

        # Try to break at paragraph boundary
        if end < len(content):
            newline_pos = content.rfind("\n\n", start, end)
            if newline_pos > start + CHUNK_SIZE // 2:
                end = newline_pos
            else:
                newline_pos = content.rfind("\n", start, end)
                if newline_pos > start + CHUNK_SIZE // 2:
                    end = newline_pos

        chunk = content[start:end].strip()
        if len(chunk) >= MIN_CHUNK_SIZE:
            chunks.append(
                {
                    "content": chunk,
                    "chunk_index": chunk_index,
                }
            )
            chunk_index += 1

        start = end - CHUNK_OVERLAP if end < len(content) else end

    return chunks


# =============================================================================
# PALACE — ChromaDB operations
# =============================================================================


def get_collection(palace_path: str):
    return get_drawer_collection(palace_path=Path(palace_path))


def relative_source_file(filepath: Path, project_path: Path) -> str:
    return filepath.relative_to(project_path).as_posix()


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:16]


def get_file_drawers(collection, source_file: str) -> tuple[list, list]:
    try:
        results = collection.get(where={"source_file": source_file}, include=["metadatas"])
        return results.get("ids", []), results.get("metadatas", [])
    except Exception:
        return [], []


def file_already_mined(collection, source_file: str, sha256: str | None = None) -> bool:
    """Fast check: has this exact file content already been filed?"""
    ids, metas = get_file_drawers(collection, source_file)
    if not ids:
        return False
    if sha256 is None:
        return True
    return any(meta.get("content_sha256") == sha256 for meta in metas if meta)


def delete_file_drawers(collection, source_file: str) -> int:
    ids, _ = get_file_drawers(collection, source_file)
    if not ids:
        return 0
    collection.delete(ids=ids)
    return len(ids)


def get_max_file_bytes() -> int:
    raw = os.environ.get("CLOUDMEM_MAX_FILE_BYTES") or os.environ.get("MEMPALACE_MAX_FILE_BYTES")
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return DEFAULT_MAX_FILE_BYTES


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _should_scan_file(filepath: Path, max_file_bytes: int) -> bool:
    if not filepath.is_file():
        return False
    if filepath.name in SKIP_FILENAMES:
        return False
    if filepath.suffix.lower() not in READABLE_EXTENSIONS:
        return False
    try:
        return filepath.stat().st_size <= max_file_bytes
    except OSError:
        return False


def _scan_project_with_git(project_path: Path, max_file_bytes: int) -> list[Path]:
    try:
        repo_root = subprocess.run(
            ["git", "-C", str(project_path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        output = subprocess.run(
            ["git", "-C", str(project_path), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            check=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    repo_path = Path(repo_root)
    files = []
    for raw_path in output.split(b"\0"):
        if not raw_path:
            continue
        filepath = repo_path / raw_path.decode("utf-8", errors="surrogateescape")
        if not _is_within(filepath, project_path):
            continue
        if _should_scan_file(filepath, max_file_bytes):
            files.append(filepath)
    return sorted(files)


def _scan_project_walk(project_path: Path, max_file_bytes: int) -> list[Path]:
    files = []
    for root, dirs, filenames in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for filename in filenames:
            filepath = Path(root) / filename
            if _should_scan_file(filepath, max_file_bytes):
                files.append(filepath)
    return sorted(files)


def add_drawer(
    collection,
    wing: str,
    room: str,
    content: str,
    source_file: str,
    chunk_index: int,
    agent: str,
    sha256: str,
):
    """Add one drawer to the palace."""
    drawer_id = (
        f"drawer_{wing}_{room}_{hashlib.md5((source_file + sha256 + str(chunk_index)).encode()).hexdigest()[:16]}"
    )
    try:
        collection.add(
            documents=[content],
            ids=[drawer_id],
            metadatas=[
                {
                    "wing": wing,
                    "room": room,
                    "source_file": source_file,
                    "chunk_index": chunk_index,
                    "added_by": agent,
                    "filed_at": datetime.now().isoformat(),
                    "content_sha256": sha256,
                    "ingest_mode": PROJECT_INGEST_MODE,
                }
            ],
        )
        return True
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            return False
        raise


# =============================================================================
# PROCESS ONE FILE
# =============================================================================


def process_file(
    filepath: Path,
    project_path: Path,
    collection,
    wing: str,
    rooms: list,
    agent: str,
    dry_run: bool,
) -> dict:
    """Read, chunk, route, and file one file. Returns drawer count."""

    source_file = relative_source_file(filepath, project_path)

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"drawers_added": 0, "status": "unreadable", "room": None}

    content = content.strip()
    sha256 = content_sha256(content) if content else ""

    if not dry_run and file_already_mined(collection, source_file, sha256):
        room = detect_room(filepath, content, rooms, project_path)
        return {"drawers_added": 0, "status": "unchanged", "room": room}

    if len(content) < MIN_CHUNK_SIZE:
        if not dry_run:
            delete_file_drawers(collection, source_file)
        return {"drawers_added": 0, "status": "too_small", "room": None}

    room = detect_room(filepath, content, rooms, project_path)
    chunks = chunk_text(content, source_file)

    if dry_run:
        print(f"    [DRY RUN] {filepath.name} → room:{room} ({len(chunks)} drawers)")
        return {"drawers_added": len(chunks), "status": "processed", "room": room}

    delete_file_drawers(collection, source_file)

    drawers_added = 0
    for chunk in chunks:
        added = add_drawer(
            collection=collection,
            wing=wing,
            room=room,
            content=chunk["content"],
            source_file=source_file,
            chunk_index=chunk["chunk_index"],
            agent=agent,
            sha256=sha256,
        )
        if added:
            drawers_added += 1

    return {"drawers_added": drawers_added, "status": "processed", "room": room}


# =============================================================================
# SCAN PROJECT
# =============================================================================


def scan_project(project_dir: str) -> list:
    """Return list of all readable file paths."""
    project_path = Path(project_dir).expanduser().resolve()
    max_file_bytes = get_max_file_bytes()
    files = _scan_project_with_git(project_path, max_file_bytes)
    if files:
        return files
    return _scan_project_walk(project_path, max_file_bytes)


# =============================================================================
# MAIN: MINE
# =============================================================================


def mine(
    project_dir: str,
    palace_path: str,
    wing_override: str = None,
    agent: str = "mempalace",
    limit: int = 0,
    dry_run: bool = False,
):
    """Mine a project directory into the palace."""

    project_path = Path(project_dir).expanduser().resolve()
    config = load_config(project_dir)

    wing = wing_override or config["wing"]
    rooms = config.get("rooms", [{"name": "general", "description": "All project files"}])

    files = scan_project(project_dir)
    if limit > 0:
        files = files[:limit]

    print(f"\n{'=' * 55}")
    print("  MemPalace Mine")
    print(f"{'=' * 55}")
    print(f"  Wing:    {wing}")
    print(f"  Rooms:   {', '.join(r['name'] for r in rooms)}")
    print(f"  Files:   {len(files)}")
    print(f"  Palace:  {palace_path}")
    if dry_run:
        print("  DRY RUN — nothing will be filed")
    print(f"{'─' * 55}\n")

    if not dry_run:
        collection = get_collection(palace_path)
    else:
        collection = None

    total_drawers = 0
    files_skipped = 0
    room_counts = defaultdict(int)

    for i, filepath in enumerate(files, 1):
        result = process_file(
            filepath=filepath,
            project_path=project_path,
            collection=collection,
            wing=wing,
            rooms=rooms,
            agent=agent,
            dry_run=dry_run,
        )
        drawers = result["drawers_added"]
        status = result["status"]
        room = result.get("room")

        if status == "unchanged" and not dry_run:
            files_skipped += 1
        else:
            total_drawers += drawers
            if room:
                room_counts[room] += 1
            if not dry_run:
                print(f"  ✓ [{i:4}/{len(files)}] {filepath.name[:50]:50} +{drawers}")

    print(f"\n{'=' * 55}")
    print("  Done.")
    print(f"  Files processed: {len(files) - files_skipped}")
    print(f"  Files skipped (already filed): {files_skipped}")
    print(f"  Drawers filed: {total_drawers}")
    print("\n  By room:")
    for room, count in sorted(room_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"    {room:20} {count} files")
    print('\n  Next: mempalace search "what you\'re looking for"')
    print(f"{'=' * 55}\n")


# =============================================================================
# STATUS
# =============================================================================


def status(palace_path: str):
    """Show what's been filed in the palace."""
    try:
        col = get_drawer_collection(palace_path=Path(palace_path), create=False)
    except Exception:
        print(f"\n  No palace found at {palace_path}")
        print("  Run: mempalace init <dir> then mempalace mine <dir>")
        return

    wing_rooms = defaultdict(lambda: defaultdict(int))
    total = 0
    for row in iter_collection_rows(col, include=["metadatas"]):
        m = row.get("metadata") or {}
        wing_rooms[m.get("wing", "?")][m.get("room", "?")] += 1
        total += 1

    print(f"\n{'=' * 55}")
    print(f"  MemPalace Status — {total} drawers")
    print(f"{'=' * 55}\n")
    for wing, rooms in sorted(wing_rooms.items()):
        print(f"  WING: {wing}")
        for room, count in sorted(rooms.items(), key=lambda x: x[1], reverse=True):
            print(f"    ROOM: {room:20} {count:5} drawers")
        print()
    print(f"{'=' * 55}\n")
