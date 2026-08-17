"""OCR engine ROI offset and backend selection."""

from src.ocr_engine import OCREngine, TextRegion, _resolve_backend


def test_text_region_fields() -> None:
    region = TextRegion(
        text="NaN",
        bbox=(1, 2, 3, 4),
        confidence=0.9,
        center=(2, 4),
        source="mock",
    )
    assert region.text == "NaN"
    assert region.center == (2, 4)


def test_offset_regions_for_roi() -> None:
    local = [
        TextRegion(text="NaN", bbox=(5, 6, 10, 8), confidence=1.0, center=(10, 10), source="mock")
    ]
    offset = OCREngine._offset_regions(local, roi=(100, 200, 50, 50))
    assert offset[0].bbox == (105, 206, 10, 8)
    assert offset[0].center == (110, 210)


def test_resolve_backend_explicit() -> None:
    assert _resolve_backend("winrt") == "winrt"
    assert _resolve_backend("pytesseract") == "pytesseract"
    assert _resolve_backend("easyocr") == "easyocr"


def test_scan_all_returns_empty_on_backend_error(monkeypatch) -> None:
    engine = OCREngine(backend="winrt")

    def boom(_img):
        raise RuntimeError("fail")

    monkeypatch.setattr(engine, "_scan_winrt", boom)
    import numpy as np

    result = engine.scan_all(np.zeros((8, 8, 3), dtype=np.uint8))
    assert result == []
