"""Locate writable app files and the bundled Tesseract binary."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_VERSION = "0.2.0"


def app_root() -> Path:
    """Directory that holds config.yaml, logs, and bundled tesseract/.

    PyInstaller onedir: folder next to the EXE.
    Source checkout: repository root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def meipass_dir() -> Path | None:
    raw = getattr(sys, "_MEIPASS", None)
    return Path(raw) if raw else None


def default_config_path() -> Path:
    return app_root() / "config.yaml"


def logs_dir() -> Path:
    path = app_root() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def find_tesseract_exe() -> Path | None:
    env = os.environ.get("TESSERACT_CMD", "").strip()
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env))
    root = app_root()
    candidates.extend(
        [
            root / "tesseract" / "tesseract.exe",
            root / "vendor" / "tesseract" / "tesseract.exe",
        ]
    )
    internal = meipass_dir()
    if internal is not None:
        candidates.append(internal / "tesseract" / "tesseract.exe")
    which = shutil.which("tesseract")
    if which:
        candidates.append(Path(which))
    for path in candidates:
        if path.is_file():
            return path.resolve()
    return None
