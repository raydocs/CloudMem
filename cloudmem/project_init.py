"""Generate per-project mempalace.yaml config for cloudmem mine."""
from pathlib import Path
import re
import yaml  # pyyaml already in dependencies

SKIP_DIRS = {
    ".git", ".svn", "__pycache__", "node_modules", ".venv", "venv",
    "env", ".env", "dist", "build", ".next", ".nuxt", "target",
    ".idea", ".vscode", ".DS_Store",
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def bootstrap_project_config(
    project_dir: str | Path,
    *,
    wing: str | None = None,
    overwrite: bool = False,
) -> Path:
    """
    Scan project_dir and write mempalace.yaml.
    Returns the path to the written config file.
    Raises FileExistsError if config already exists and overwrite=False.
    """
    project_dir = Path(project_dir).resolve()
    config_path = project_dir / "mempalace.yaml"

    if config_path.exists() and not overwrite:
        return config_path  # already exists, silently return

    wing_name = wing or _slug(project_dir.name) or "project"

    # Discover top-level subdirs (skip hidden/build dirs)
    subdirs = sorted([
        d for d in project_dir.iterdir()
        if d.is_dir() and d.name not in SKIP_DIRS and not d.name.startswith(".")
    ])

    rooms = []
    if subdirs:
        for d in subdirs[:10]:  # cap at 10 rooms
            rooms.append({
                "name": _slug(d.name),
                "description": f"Files under {d.name}/",
                "keywords": [d.name],
            })
    # always add a general catch-all
    rooms.append({
        "name": "general",
        "description": "Uncategorized files",
        "keywords": [],
    })

    config = {
        "wing": wing_name,
        "rooms": rooms,
    }

    config_path.write_text(yaml.dump(config, default_flow_style=False, allow_unicode=True))
    return config_path
