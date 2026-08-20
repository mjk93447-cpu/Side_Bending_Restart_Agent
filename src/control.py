"""PyAutoGUI mouse control with FAILSAFE. Pattern from SOP control_engine."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.config import ControlConfig


def shell_execute_runas(path: str, arguments: str = "") -> int:
    """Start a file with the Windows 'runas' verb (Run as administrator)."""
    import ctypes

    return int(
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            path,
            arguments or None,
            None,
            1,
        )
    )


try:
    import pyautogui
except Exception as exc:  # pragma: no cover - display/import dependent
    pyautogui = None
    PYAUTOGUI_IMPORT_ERROR = exc
else:
    PYAUTOGUI_IMPORT_ERROR = None


@dataclass
class ControlResult:
    success: bool
    coords: Optional[tuple[int, int]]
    duration: float
    error: str = ""


class ControlEngine:
    def __init__(self, config: ControlConfig | None = None) -> None:
        self.config = config or ControlConfig()
        if pyautogui is not None:
            pyautogui.FAILSAFE = bool(self.config.failsafe)

    def _ensure_available(self) -> None:
        if pyautogui is None:
            raise RuntimeError("pyautogui is unavailable") from PYAUTOGUI_IMPORT_ERROR

    def click_at(self, x: int, y: int) -> ControlResult:
        start = time.perf_counter()
        try:
            self._ensure_available()
            pyautogui.moveTo(x, y, duration=self.config.move_duration)
            pyautogui.click()
            time.sleep(self.config.click_pause)
            return ControlResult(True, (x, y), time.perf_counter() - start)
        except Exception as exc:
            return ControlResult(False, (x, y), time.perf_counter() - start, error=str(exc))

    def double_click_at(self, x: int, y: int) -> ControlResult:
        start = time.perf_counter()
        try:
            self._ensure_available()
            pyautogui.moveTo(x, y, duration=self.config.move_duration)
            pyautogui.doubleClick()
            time.sleep(self.config.click_pause)
            return ControlResult(True, (x, y), time.perf_counter() - start)
        except Exception as exc:
            return ControlResult(False, (x, y), time.perf_counter() - start, error=str(exc))

    def wait(self, sec: float) -> None:
        time.sleep(float(sec))

    def launch_as_admin(self, path: str, arguments: str = "") -> ControlResult:
        start = time.perf_counter()
        resolved = os.path.expandvars(str(path or "").strip().strip('"'))
        if not resolved:
            return ControlResult(False, None, time.perf_counter() - start, error="launch path is empty")
        target = Path(resolved)
        if not target.is_file():
            return ControlResult(
                False,
                None,
                time.perf_counter() - start,
                error=f"launch path not found: {resolved}",
            )
        try:
            rc = shell_execute_runas(str(target), arguments)
        except Exception as exc:
            return ControlResult(False, None, time.perf_counter() - start, error=str(exc))
        ok = int(rc) > 32
        error = "" if ok else f"ShellExecute runas failed (code {rc})"
        return ControlResult(ok, None, time.perf_counter() - start, error=error)
