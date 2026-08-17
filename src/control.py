"""PyAutoGUI mouse control with FAILSAFE. Pattern from SOP control_engine."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from src.config import ControlConfig

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
