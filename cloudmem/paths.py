"""Unified path helpers for CloudMem — all persistent state lives under ~/.cloudmem."""

from pathlib import Path
import os


def get_cloudmem_home() -> Path:
    p = Path(os.environ.get("CLOUDMEM_HOME", Path.home() / ".cloudmem"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_palace_path() -> Path:
    env = os.environ.get("CLOUDMEM_PALACE_PATH")
    if env:
        return Path(env)
    return get_cloudmem_home() / "palace"


def get_config_path() -> Path:
    return get_cloudmem_home() / "config.json"


def get_identity_path() -> Path:
    return get_cloudmem_home() / "identity.txt"


def get_entity_registry_path() -> Path:
    return get_cloudmem_home() / "entity_registry.json"


def get_knowledge_graph_path() -> Path:
    return get_cloudmem_home() / "knowledge_graph.sqlite3"


def get_known_names_path() -> Path:
    return get_cloudmem_home() / "known_names.json"


def get_people_map_path() -> Path:
    return get_cloudmem_home() / "people_map.json"


def get_legacy_mempalace_home() -> Path:
    return Path.home() / ".mempalace"


def legacy_fallback(new_path: Path, legacy_rel: str) -> Path:
    """Return new_path if it exists, else fall back to ~/.mempalace/<legacy_rel>."""
    if new_path.exists():
        return new_path
    legacy = get_legacy_mempalace_home() / legacy_rel
    if legacy.exists():
        return legacy
    return new_path  # default to new location even if not yet created
