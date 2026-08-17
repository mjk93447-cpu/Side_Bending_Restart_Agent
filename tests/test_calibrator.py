"""Calibrator helpers update ROI and named click points."""

from src.calibrator import apply_point, apply_roi
from src.config import load_config


def test_apply_roi_normalizes_drag_order() -> None:
    cfg = load_config()
    apply_roi(cfg, "table", 400, 800, 100, 200)
    roi = cfg.rois["table"]
    assert (roi.x, roi.y, roi.w, roi.h) == (100, 200, 300, 600)


def test_apply_point_keeps_click_type() -> None:
    cfg = load_config()
    apply_point(cfg, "launch_icon", 12, 34)
    assert cfg.points["launch_icon"].x == 12
    assert cfg.points["launch_icon"].y == 34
    assert cfg.points["launch_icon"].click == "double"
    apply_point(cfg, "stop", 9, 8)
    assert cfg.points["stop"].click == "single"
    apply_point(cfg, "confirm_yes", 100, 200)
    assert cfg.points["confirm_yes"].x == 100
    assert cfg.points["confirm_yes"].click == "single"
