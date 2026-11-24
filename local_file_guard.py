"""Shared guard for both development static servers, including HEAD."""
from pathlib import Path
from urllib.parse import unquote, urlsplit

BLOCKED = {"work", "node_modules", "__pycache__"}
SUFFIXES = (".py", ".pyc", ".pyo", ".sqlite", ".sqlite3", ".db", "-wal", "-shm", ".key", ".pem")

def blocked_path(root, handler):
    decoded = unquote(urlsplit(handler.path).path)
    try:
        rel = Path(handler.translate_path(handler.path)).resolve().relative_to(Path(root).resolve())
    except (OSError, RuntimeError, ValueError):
        return True
    for path in (Path(decoded), rel):
        if any(part.startswith(".") or part in BLOCKED for part in path.parts if part not in ("/", "")):
            return True
        if str(path).lower().endswith(SUFFIXES):
            return True
    return False
