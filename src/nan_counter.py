"""Count NaN (or custom) tokens in OCR regions."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import numpy as np

from src.ocr_engine import TextRegion

logger = logging.getLogger(__name__)

DEFAULT_NAN_PATTERN = r"(?i)\bnan\b"
N0N_PATTERN = r"(?i)\bn[a0]n\b"


def count_nan_tokens(
    regions: list[TextRegion],
    pattern: Optional[str] = None,
    n0n_correction: bool = False,
) -> int:
    regex = re.compile(pattern or (N0N_PATTERN if n0n_correction else DEFAULT_NAN_PATTERN))
    total = 0
    for region in regions:
        text = region.text or ""
        total += len(regex.findall(text))
    return total


def count_nan_in_image(
    img_np: np.ndarray,
    ocr: Any,
    roi: Optional[tuple] = None,
    pattern: Optional[str] = None,
    n0n_correction: bool = False,
) -> tuple[int, list[TextRegion]]:
    try:
        regions = ocr.scan_all(img_np, roi=roi) or []
    except Exception as exc:
        logger.warning("OCR failed while counting NaN tokens: %s", exc)
        return 0, []
    return count_nan_tokens(regions, pattern=pattern, n0n_correction=n0n_correction), regions
