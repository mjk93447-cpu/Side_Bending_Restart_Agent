"""Load and save agent YAML configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


@dataclass
class MonitorConfig:
    interval_sec: float = 2.0
    confirm_scans: int = 2
    cooldown_sec: float = 15.0


@dataclass
class OcrConfig:
    backend: str = "auto"
    n0n_correction: bool = False


@dataclass
class ControlConfig:
    move_duration: float = 0.30
    click_pause: float = 0.50
    failsafe: bool = True


@dataclass
class Roi:
    x: int
    y: int
    w: int
    h: int

    def as_xywh(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> Roi:
        if "w" in data and "h" in data:
            return cls(
                x=int(data["x"]),
                y=int(data["y"]),
                w=int(data["w"]),
                h=int(data["h"]),
            )
        if "x1" in data and "x2" in data:
            x1, y1 = int(data["x1"]), int(data["y1"])
            x2, y2 = int(data["x2"]), int(data["y2"])
            return cls(x=x1, y=y1, w=x2 - x1, h=y2 - y1)
        if isinstance(data, (list, tuple)) and len(data) == 4:
            x1, y1, x2, y2 = (int(v) for v in data)
            return cls(x=x1, y=y1, w=x2 - x1, h=y2 - y1)
        raise ValueError(f"Unsupported ROI mapping: {data!r}")


@dataclass
class Point:
    x: int
    y: int
    click: str = "single"


@dataclass
class RecoveryConfig:
    startup_wait_sec: float = 10.0
    sequences: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


@dataclass
class AppConfig:
    monitor: MonitorConfig
    ocr: OcrConfig
    control: ControlConfig
    rois: dict[str, Roi]
    points: dict[str, Point]
    recovery: RecoveryConfig
    rules: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "monitor": asdict(self.monitor),
            "ocr": asdict(self.ocr),
            "control": asdict(self.control),
            "rois": {
                name: {"x": roi.x, "y": roi.y, "w": roi.w, "h": roi.h}
                for name, roi in self.rois.items()
            },
            "points": {
                name: {"x": pt.x, "y": pt.y, "click": pt.click}
                for name, pt in self.points.items()
            },
            "recovery": {
                "startup_wait_sec": self.recovery.startup_wait_sec,
                "sequences": self.recovery.sequences,
            },
            "rules": self.rules,
        }


def load_config(path: str | Path | None = None) -> AppConfig:
    cfg_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    with cfg_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return _parse_config(raw)


def save_config(path: str | Path, config: AppConfig) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config.to_dict(), handle, sort_keys=False, allow_unicode=True)


def _parse_config(raw: dict[str, Any]) -> AppConfig:
    monitor_raw = raw.get("monitor") or {}
    ocr_raw = raw.get("ocr") or {}
    control_raw = raw.get("control") or {}
    recovery_raw = raw.get("recovery") or {}

    rois = {
        name: Roi.from_mapping(mapping)
        for name, mapping in (raw.get("rois") or {}).items()
    }
    points = {
        name: Point(
            x=int(mapping["x"]),
            y=int(mapping["y"]),
            click=str(mapping.get("click", "single")),
        )
        for name, mapping in (raw.get("points") or {}).items()
    }
    return AppConfig(
        monitor=MonitorConfig(
            interval_sec=float(monitor_raw.get("interval_sec", 2.0)),
            confirm_scans=int(monitor_raw.get("confirm_scans", 2)),
            cooldown_sec=float(monitor_raw.get("cooldown_sec", 15.0)),
        ),
        ocr=OcrConfig(
            backend=str(ocr_raw.get("backend", "auto")),
            n0n_correction=bool(ocr_raw.get("n0n_correction", False)),
        ),
        control=ControlConfig(
            move_duration=float(control_raw.get("move_duration", 0.30)),
            click_pause=float(control_raw.get("click_pause", 0.50)),
            failsafe=bool(control_raw.get("failsafe", True)),
        ),
        rois=rois,
        points=points,
        recovery=RecoveryConfig(
            startup_wait_sec=float(recovery_raw.get("startup_wait_sec", 10)),
            sequences=dict(recovery_raw.get("sequences") or {}),
        ),
        rules=list(raw.get("rules") or []),
    )
