"""Screen OCR engine: WinRT first, then Tesseract, then EasyOCR.

Pattern adapted from connector-vision-sop-agent src/ocr_engine.py.
YOLO / PaddleOCR / Ollama are intentionally omitted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_WINRT_AVAILABLE: Optional[bool] = None
_TESSERACT_AVAILABLE: Optional[bool] = None
_EASYOCR_AVAILABLE: Optional[bool] = None


def _check_winrt() -> bool:
    global _WINRT_AVAILABLE
    if _WINRT_AVAILABLE is not None:
        return _WINRT_AVAILABLE
    try:
        import winsdk.windows.graphics.imaging  # noqa: F401
        import winsdk.windows.media.ocr  # noqa: F401

        _WINRT_AVAILABLE = True
    except Exception:
        _WINRT_AVAILABLE = False
    return _WINRT_AVAILABLE


def _check_pytesseract() -> bool:
    global _TESSERACT_AVAILABLE
    if _TESSERACT_AVAILABLE is not None:
        return _TESSERACT_AVAILABLE
    try:
        import pytesseract  # noqa: F401

        _TESSERACT_AVAILABLE = True
    except Exception:
        _TESSERACT_AVAILABLE = False
    return _TESSERACT_AVAILABLE


def _check_easyocr() -> bool:
    global _EASYOCR_AVAILABLE
    if _EASYOCR_AVAILABLE is not None:
        return _EASYOCR_AVAILABLE
    try:
        import easyocr  # noqa: F401

        _EASYOCR_AVAILABLE = True
    except Exception:
        _EASYOCR_AVAILABLE = False
    return _EASYOCR_AVAILABLE


def _resolve_backend(requested: str) -> str:
    if requested in ("winrt", "pytesseract", "easyocr"):
        return requested
    if _check_winrt():
        return "winrt"
    if _check_pytesseract():
        return "pytesseract"
    if _check_easyocr():
        return "easyocr"
    return "winrt"


@dataclass
class TextRegion:
    text: str
    bbox: tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float
    center: tuple[int, int]
    source: str


class OCREngine:
    """WinRT OCR with optional pytesseract / EasyOCR fallbacks."""

    def __init__(self, backend: str = "auto") -> None:
        self._backend = _resolve_backend(backend)
        self._easyocr_reader: Optional[object] = None

    @property
    def backend(self) -> str:
        return self._backend

    def scan_all(
        self,
        img_np: np.ndarray,
        roi: Optional[tuple] = None,
    ) -> List[TextRegion]:
        try:
            if roi is not None:
                rx, ry, rw, rh = (int(v) for v in roi)
                scan_img = img_np[ry : ry + rh, rx : rx + rw]
            else:
                scan_img = img_np
            if scan_img is None or scan_img.size == 0:
                return []

            if self._backend == "winrt":
                regions = self._scan_winrt(scan_img)
            elif self._backend == "easyocr":
                regions = self._scan_easyocr(scan_img)
            else:
                regions = self._scan_pytesseract(scan_img)

            if roi is not None:
                return self._offset_regions(regions, roi)
            return regions
        except Exception as exc:
            logger.warning("OCR scan_all error (%s): %s", self._backend, exc)
            return []

    @staticmethod
    def _offset_regions(regions: List[TextRegion], roi: tuple) -> List[TextRegion]:
        rx, ry = int(roi[0]), int(roi[1])
        offset: List[TextRegion] = []
        for region in regions:
            bx, by, bw, bh = region.bbox
            offset.append(
                TextRegion(
                    text=region.text,
                    bbox=(bx + rx, by + ry, bw, bh),
                    confidence=region.confidence,
                    center=(region.center[0] + rx, region.center[1] + ry),
                    source=region.source,
                )
            )
        return offset

    def _scan_winrt(self, img_np: np.ndarray) -> List[TextRegion]:
        import asyncio

        import winsdk.windows.graphics.imaging as wgi
        import winsdk.windows.media.ocr as wocr
        import winsdk.windows.storage.streams as wss

        h, w = img_np.shape[:2]
        bgra = cv2.cvtColor(img_np, cv2.COLOR_BGR2BGRA)
        raw_bytes = bgra.tobytes()
        writer = wss.DataWriter()
        writer.write_bytes(raw_bytes)
        ibuf = writer.detach_buffer()
        bmp = wgi.SoftwareBitmap.create_copy_from_buffer(
            ibuf,
            wgi.BitmapPixelFormat.BGRA8,
            w,
            h,
            wgi.BitmapAlphaMode.PREMULTIPLIED,
        )
        ocr_engine = wocr.OcrEngine.try_create_from_user_profile_languages()
        if ocr_engine is None:
            try:
                import winsdk.windows.globalization as wg

                ocr_engine = wocr.OcrEngine.try_create_from_language(wg.Language("en-US"))
            except Exception as exc:
                logger.debug("WinRT en-US fallback failed: %s", exc)
                ocr_engine = None
        if ocr_engine is None:
            raise RuntimeError("WinRT OcrEngine language pack is not available")

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(ocr_engine.recognize_async(bmp))
        finally:
            loop.close()

        regions: List[TextRegion] = []
        for line in result.lines:
            for word in line.words:
                rect = word.bounding_rect
                x = int(rect.x)
                y = int(rect.y)
                ww = int(rect.width)
                wh = int(rect.height)
                regions.append(
                    TextRegion(
                        text=word.text,
                        bbox=(x, y, ww, wh),
                        confidence=1.0,
                        center=(x + ww // 2, y + wh // 2),
                        source="winrt",
                    )
                )
        return regions

    def _scan_pytesseract(self, img_np: np.ndarray) -> List[TextRegion]:
        import pytesseract

        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
        regions: List[TextRegion] = []
        n_items = len(data.get("text") or [])
        for index in range(n_items):
            text = str(data["text"][index]).strip()
            if not text:
                continue
            x = int(data["left"][index])
            y = int(data["top"][index])
            ww = int(data["width"][index])
            wh = int(data["height"][index])
            try:
                conf = float(data["conf"][index])
            except (TypeError, ValueError):
                conf = 0.0
            if conf < 0:
                conf = 0.0
            regions.append(
                TextRegion(
                    text=text,
                    bbox=(x, y, ww, wh),
                    confidence=conf / 100.0 if conf > 1 else conf,
                    center=(x + ww // 2, y + wh // 2),
                    source="pytesseract",
                )
            )
        return regions

    def _scan_easyocr(self, img_np: np.ndarray) -> List[TextRegion]:
        reader = self._get_easyocr()
        if reader is None:
            return []
        rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        raw = reader.readtext(rgb)
        regions: List[TextRegion] = []
        for bbox_pts, text, conf in raw or []:
            xs = [int(p[0]) for p in bbox_pts]
            ys = [int(p[1]) for p in bbox_pts]
            x_min, y_min = min(xs), min(ys)
            bw = max(xs) - x_min
            bh = max(ys) - y_min
            regions.append(
                TextRegion(
                    text=str(text),
                    bbox=(x_min, y_min, bw, bh),
                    confidence=float(conf),
                    center=(x_min + bw // 2, y_min + bh // 2),
                    source="easyocr",
                )
            )
        return regions

    def _get_easyocr(self) -> Optional[object]:
        if self._easyocr_reader is not None:
            return self._easyocr_reader
        try:
            import easyocr

            self._easyocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        except Exception as exc:
            logger.warning("EasyOCR initialization failed: %s", exc)
            self._easyocr_reader = None
        return self._easyocr_reader
