"""Opt-in per-user startup entry; never touches Windows security policy."""
import os
from pathlib import Path


def startup_path():
    return Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup/June.cmd"


def set_startup(config, enabled):
    path = startup_path()
    expected = f'@echo off\nrem Managed by June\ncd /d "{config.root}"\nstart "June" "{config.root / ".venv/Scripts/pythonw.exe"}" -m june desktop --minimized\n'
    if path.exists() and "rem Managed by June" not in path.read_text(errors="replace"):
        raise PermissionError("Existing startup file is not owned by June")
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected, encoding="utf-8")
    elif path.exists():
        path.unlink()
    return {"enabled": enabled, "path": str(path)}
