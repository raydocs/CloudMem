"""
MemPalace configuration system.

Priority: env vars > config file (~/.cloudmem/config.json) > defaults
"""

import json
import os
from pathlib import Path

from cloudmem.paths import (
    get_cloudmem_home as get_unified_cloudmem_home,
    get_config_path,
    get_palace_path as get_unified_palace_path,
    get_people_map_path,
)

DEFAULT_CLOUDMEM_HOME = str(get_unified_cloudmem_home())
DEFAULT_PALACE_PATH = str(get_unified_palace_path())
DEFAULT_COLLECTION_NAME = "mempalace_drawers"


def get_palace_path() -> str:
    """Return the palace path from env or default config."""
    env_val = os.environ.get("CLOUDMEM_PALACE_PATH") or os.environ.get("MEMPALACE_PALACE_PATH")
    if env_val:
        return env_val
    return str(get_unified_palace_path())


def get_cloudmem_home() -> str:
    """Return the CloudMem storage root directory."""
    return str(get_unified_cloudmem_home())


DEFAULT_TOPIC_WINGS = [
    "emotions",
    "consciousness",
    "memory",
    "technical",
    "identity",
    "family",
    "creative",
]

DEFAULT_HALL_KEYWORDS = {
    "emotions": [
        "scared",
        "afraid",
        "worried",
        "happy",
        "sad",
        "love",
        "hate",
        "feel",
        "cry",
        "tears",
    ],
    "consciousness": [
        "consciousness",
        "conscious",
        "aware",
        "real",
        "genuine",
        "soul",
        "exist",
        "alive",
    ],
    "memory": ["memory", "remember", "forget", "recall", "archive", "palace", "store"],
    "technical": [
        "code",
        "python",
        "script",
        "bug",
        "error",
        "function",
        "api",
        "database",
        "server",
    ],
    "identity": ["identity", "name", "who am i", "persona", "self"],
    "family": ["family", "kids", "children", "daughter", "son", "parent", "mother", "father"],
    "creative": ["game", "gameplay", "player", "app", "design", "art", "music", "story"],
}


class MempalaceConfig:
    """Configuration manager for MemPalace.

    Load order: env vars > config file > defaults.
    """

    def __init__(self, config_dir=None):
        """Initialize config.

        Args:
            config_dir: Override config directory (useful for testing).
                        Defaults to ~/.cloudmem.
        """
        self._config_file = Path(config_dir) / "config.json" if config_dir else get_config_path()
        self._config_dir = self._config_file.parent
        self._people_map_file = (
            Path(config_dir) / "people_map.json" if config_dir else get_people_map_path()
        )
        self._file_config = {}

        if self._config_file.exists():
            try:
                with open(self._config_file, "r") as f:
                    self._file_config = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._file_config = {}

    @property
    def palace_path(self):
        """Path to the memory palace data directory."""
        env_val = (
            os.environ.get("CLOUDMEM_PALACE_PATH")
            or os.environ.get("MEMPALACE_PALACE_PATH")
            or os.environ.get("MEMPAL_PALACE_PATH")
        )
        if env_val:
            return env_val
        return self._file_config.get("palace_path", str(get_unified_palace_path()))

    @property
    def collection_name(self):
        """ChromaDB collection name."""
        return self._file_config.get("collection_name", DEFAULT_COLLECTION_NAME)

    @property
    def people_map(self):
        """Mapping of name variants to canonical names."""
        if self._people_map_file.exists():
            try:
                with open(self._people_map_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return self._file_config.get("people_map", {})

    @property
    def topic_wings(self):
        """List of topic wing names."""
        return self._file_config.get("topic_wings", DEFAULT_TOPIC_WINGS)

    @property
    def hall_keywords(self):
        """Mapping of hall names to keyword lists."""
        return self._file_config.get("hall_keywords", DEFAULT_HALL_KEYWORDS)

    def init(self):
        """Create config directory and write default config.json if it doesn't exist."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        if not self._config_file.exists():
            default_config = {
                "palace_path": str(get_unified_palace_path()),
                "collection_name": DEFAULT_COLLECTION_NAME,
                "topic_wings": DEFAULT_TOPIC_WINGS,
                "hall_keywords": DEFAULT_HALL_KEYWORDS,
            }
            with open(self._config_file, "w") as f:
                json.dump(default_config, f, indent=2)
        return self._config_file

    def save_people_map(self, people_map):
        """Write people_map.json to config directory.

        Args:
            people_map: Dict mapping name variants to canonical names.
        """
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._people_map_file, "w") as f:
            json.dump(people_map, f, indent=2)
        return self._people_map_file


# Alias: CloudMemConfig is the same as MempalaceConfig
CloudMemConfig = MempalaceConfig
