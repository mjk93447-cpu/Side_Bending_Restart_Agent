"""Config loader defaults and ROI / recovery parsing."""

from pathlib import Path

from src.config import DEFAULT_CONFIG_PATH, load_config, save_config
from src.paths import APP_VERSION


def test_load_default_config_threshold_and_wait(tmp_path: Path) -> None:
    src = Path("config.yaml")
    dest = tmp_path / "config.yaml"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    cfg = load_config(dest)

    assert cfg.monitor.interval_sec == 2.0
    assert cfg.monitor.confirm_scans == 2
    assert cfg.monitor.cooldown_sec == 15.0
    assert cfg.ocr.backend == "auto"
    assert cfg.ocr.n0n_correction is False
    assert cfg.control.failsafe is True
    assert cfg.recovery.startup_wait_sec == 10

    rule = next(r for r in cfg.rules if r["name"] == "nan_table_freeze")
    assert rule["enabled"] is True
    assert rule["then"] == "restart_app"
    cond = rule["when"]["all"][0]
    assert cond["type"] == "ocr_count"
    assert cond["roi"] == "table"
    assert cond["min"] == 21


def test_roi_xywh_and_x1y1x2y2(tmp_path: Path) -> None:
    dest = tmp_path / "config.yaml"
    dest.write_text(
        """
monitor:
  interval_sec: 1
  confirm_scans: 1
  cooldown_sec: 1
ocr:
  backend: auto
  n0n_correction: false
control:
  move_duration: 0.1
  click_pause: 0.1
  failsafe: true
rois:
  table:
    x1: 100
    y1: 200
    x2: 400
    y2: 500
points:
  stop: {x: 1, y: 2, click: single}
  close: {x: 3, y: 4, click: single}
  launch_icon: {x: 5, y: 6, click: double}
  start: {x: 7, y: 8, click: single}
recovery:
  startup_wait_sec: 10
  sequences:
    restart_app: []
rules: []
""",
        encoding="utf-8",
    )
    cfg = load_config(dest)
    roi = cfg.rois["table"]
    assert (roi.x, roi.y, roi.w, roi.h) == (100, 200, 300, 300)
    assert roi.as_xywh() == (100, 200, 300, 300)


def test_save_roundtrip_updates_point(tmp_path: Path) -> None:
    dest = tmp_path / "config.yaml"
    dest.write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    cfg = load_config(dest)
    cfg.points["stop"].x = 111
    cfg.points["stop"].y = 222
    save_config(dest, cfg)
    reloaded = load_config(dest)
    assert reloaded.points["stop"].x == 111
    assert reloaded.points["stop"].y == 222
    assert reloaded.points["launch_icon"].click == "double"


def test_default_config_path_exists() -> None:
    assert DEFAULT_CONFIG_PATH.name == "config.yaml"
    assert DEFAULT_CONFIG_PATH.exists()


def test_packaged_version_is_0_2_0() -> None:
    text = Path("config.yaml").read_text(encoding="utf-8")
    assert 'version: "0.2.0"' in text
    assert APP_VERSION == "0.2.0"
