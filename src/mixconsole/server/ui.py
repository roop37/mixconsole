"""Locate the built console (apps/console/dist) for ``mixconsole serve --ui``."""

import os
from pathlib import Path


def find_ui_dir(explicit: Path | None = None) -> Path | None:
    """First folder with an ``index.html``: explicit, $MIXCONSOLE_UI_DIR, packaged, repo build."""
    if explicit is not None:  # an explicit folder is never silently replaced by a default
        return explicit if (explicit / "index.html").is_file() else None
    here = Path(__file__).resolve()
    env = os.environ.get("MIXCONSOLE_UI_DIR")
    candidates = [
        Path(env) if env else None,
        here.parents[1] / "_ui",
        here.parents[3] / "apps" / "console" / "dist",
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "index.html").is_file():
            return candidate
    return None
