"""Speaker: lectura en voz alta de asistentes de IA de terminal."""

from __future__ import annotations

import subprocess
from pathlib import Path

# Única fuente de la versión (pyproject.toml la lee de aquí). Ver CHANGELOG.md.
__version__ = "0.3.0"


def full_version() -> str:
    """Versión con el commit de git cuando se ejecuta desde el repositorio,
    p. ej. "0.2.0 (873e85a)" o "0.2.0 (873e85a, con cambios sin commit)"."""
    repo = Path(__file__).resolve().parents[2]
    if not (repo / ".git").exists():
        return __version__
    try:
        def git(*args: str) -> str:
            return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                                  text=True, timeout=2, check=True).stdout.strip()
        commit = git("rev-parse", "--short", "HEAD")
        dirty = ", con cambios sin commit" if git("status", "--porcelain", "--untracked-files=no") else ""
        return f"{__version__} ({commit}{dirty})"
    except (OSError, subprocess.SubprocessError):
        return __version__
