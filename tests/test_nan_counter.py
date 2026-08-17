"""NaN token counting from OCR regions and ROI scans."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.nan_counter import count_nan_tokens, count_nan_in_image
from src.ocr_engine import TextRegion


def _region(text: str, x: int = 0, y: int = 0) -> TextRegion:
    return TextRegion(text=text, bbox=(x, y, 20, 10), confidence=1.0, center=(x + 10, y + 5), source="mock")


def test_count_exact_nan_case_insensitive() -> None:
    regions = [_region("NaN"), _region("nan"), _region("NAN"), _region("OK")]
    assert count_nan_tokens(regions) == 3


def test_count_splits_multiple_nans_in_one_box() -> None:
    regions = [_region("NaN NaN NaN"), _region("value")]
    assert count_nan_tokens(regions) == 3


def test_count_does_not_match_partial_words() -> None:
    regions = [_region("banana"), _region("NaNosecond")]
    assert count_nan_tokens(regions) == 0


def test_n0n_correction_off_by_default() -> None:
    regions = [_region("N0N"), _region("NaN")]
    assert count_nan_tokens(regions) == 1
    assert count_nan_tokens(regions, n0n_correction=True) == 2


def test_custom_pattern() -> None:
    regions = [_region("ERR"), _region("ERR"), _region("ok")]
    assert count_nan_tokens(regions, pattern=r"(?i)\berr\b") == 2


def test_empty_or_blank_regions() -> None:
    assert count_nan_tokens([]) == 0
    assert count_nan_tokens([_region("   "), _region("")]) == 0


@dataclass
class _FakeOcr:
    regions: list[TextRegion]
    last_roi: tuple | None = None

    def scan_all(self, img_np, roi=None):
        self.last_roi = roi
        return list(self.regions)


def test_count_nan_in_image_uses_roi_and_ocr() -> None:
    fake = _FakeOcr([_region("NaN") for _ in range(21)] + [_region("1.0")])
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    roi = (10, 20, 30, 40)
    count, regions = count_nan_in_image(image, fake, roi=roi)
    assert count == 21
    assert fake.last_roi == roi
    assert len(regions) == 22


def test_ocr_failure_counts_as_zero() -> None:
    class Boom:
        def scan_all(self, img_np, roi=None):
            raise RuntimeError("ocr down")

    image = np.zeros((10, 10, 3), dtype=np.uint8)
    count, regions = count_nan_in_image(image, Boom(), roi=None)
    assert count == 0
    assert regions == []
