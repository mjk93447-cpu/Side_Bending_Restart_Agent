"""Screen capture using pyautogui so click coordinates share the same DPI space."""

from __future__ import annotations

import cv2
import numpy as np

try:
    import pyautogui
except Exception as exc:  # pragma: no cover
    pyautogui = None
    PYAUTOGUI_IMPORT_ERROR = exc
else:
    PYAUTOGUI_IMPORT_ERROR = None


def capture_screen(region: tuple[int, int, int, int] | None = None) -> np.ndarray:
    """Return a BGR screenshot. region is (x, y, w, h) when given."""
    if pyautogui is None:
        raise RuntimeError("pyautogui is unavailable") from PYAUTOGUI_IMPORT_ERROR
    screenshot = pyautogui.screenshot(region=region)
    rgb = np.array(screenshot)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
