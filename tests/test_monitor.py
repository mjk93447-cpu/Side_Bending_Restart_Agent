"""Monitor confirm_scans, cooldown, and recovery dispatch."""

from __future__ import annotations

import numpy as np

from src.config import load_config
from src.monitor import Monitor
from src.ocr_engine import TextRegion


class FakeOcr:
    def __init__(self, count: int) -> None:
        self.count = count

    def scan_all(self, img_np, roi=None):
        return [
            TextRegion("NaN", (0, 0, 8, 8), 1.0, (4, 4), "mock") for _ in range(self.count)
        ]


class FakeControl:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def click_at(self, x, y):
        self.calls.append(("click", x, y))

    def double_click_at(self, x, y):
        self.calls.append(("double", x, y))

    def wait(self, sec):
        self.calls.append(("wait", sec))

    def launch_as_admin(self, path, arguments=""):
        self.calls.append(("launch_admin", path, arguments))
        from src.control import ControlResult

        return ControlResult(True, None, 0.0)


def _image() -> np.ndarray:
    return np.zeros((1080, 1920, 3), dtype=np.uint8)


def test_below_threshold_does_not_recover() -> None:
    cfg = load_config()
    cfg.monitor.confirm_scans = 1
    control = FakeControl()
    monitor = Monitor(cfg, ocr=FakeOcr(20), control=control, dry_run=False)
    tick = monitor.process_frame(_image(), now=0.0)
    assert tick.triggered is False
    assert tick.nan_count == 20
    assert control.calls == []


def test_confirm_scans_required_before_trigger() -> None:
    cfg = load_config()
    cfg.monitor.confirm_scans = 2
    cfg.monitor.cooldown_sec = 0
    control = FakeControl()
    monitor = Monitor(cfg, ocr=FakeOcr(21), control=control, dry_run=False)
    first = monitor.process_frame(_image(), now=1.0)
    assert first.triggered is False
    assert first.confirm_hits == 1
    second = monitor.process_frame(_image(), now=3.0)
    assert second.triggered is True
    assert second.sequence == "restart_app"
    assert ("click", cfg.points["stop"].x, cfg.points["stop"].y) in control.calls
    assert any(c[0] == "launch_admin" for c in control.calls)


def test_reset_confirm_when_count_drops() -> None:
    cfg = load_config()
    cfg.monitor.confirm_scans = 2
    ocr = FakeOcr(21)
    monitor = Monitor(cfg, ocr=ocr, control=FakeControl(), dry_run=True)
    monitor.process_frame(_image(), now=0.0)
    ocr.count = 0
    tick = monitor.process_frame(_image(), now=2.0)
    assert tick.confirm_hits == 0
    assert tick.triggered is False


def test_cooldown_blocks_immediate_retrigger() -> None:
    cfg = load_config()
    cfg.monitor.confirm_scans = 1
    cfg.monitor.cooldown_sec = 15
    control = FakeControl()
    monitor = Monitor(cfg, ocr=FakeOcr(30), control=control, dry_run=False)
    first = monitor.process_frame(_image(), now=10.0)
    assert first.triggered is True
    n_calls = len(control.calls)
    second = monitor.process_frame(_image(), now=20.0)
    assert second.triggered is False
    assert len(control.calls) == n_calls
    third = monitor.process_frame(_image(), now=26.0)
    assert third.triggered is True
    assert len(control.calls) > n_calls


def test_dry_run_skips_real_clicks() -> None:
    cfg = load_config()
    cfg.monitor.confirm_scans = 1
    cfg.monitor.cooldown_sec = 0
    control = FakeControl()
    monitor = Monitor(cfg, ocr=FakeOcr(21), control=control, dry_run=True)
    tick = monitor.process_frame(_image(), now=0.0)
    assert tick.triggered is True
    assert control.calls == []
