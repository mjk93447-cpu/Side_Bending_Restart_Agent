"""Load and save agent YAML configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.paths import default_config_path, meipass_dir

DEFAULT_CONFIG_PATH = default_config_path()


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
    stop_confirm_wait_sec: float = 1.0
    editor_managed: bool = False
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
                "stop_confirm_wait_sec": self.recovery.stop_confirm_wait_sec,
                "editor_managed": self.recovery.editor_managed,
                "sequences": self.recovery.sequences,
            },
            "rules": self.rules,
        }


def ensure_config_file(path: str | Path | None = None) -> Path:
    """Return a writable config.yaml, copying the bundled default if needed."""
    dest = Path(path) if path is not None else default_config_path()
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    for candidate in (
        (meipass_dir() / "config.yaml") if meipass_dir() is not None else None,
        Path(__file__).resolve().parent.parent / "config.yaml",
    ):
        if candidate is not None and candidate.exists() and candidate != dest:
            dest.write_text(candidate.read_text(encoding="utf-8"), encoding="utf-8")
            return dest
    raise FileNotFoundError(f"config.yaml not found at {dest}")


def load_config(path: str | Path | None = None) -> AppConfig:
    cfg_path = ensure_config_file(path)
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
        _normalize_point_name(name): Point(
            x=int(mapping["x"]),
            y=int(mapping["y"]),
            click=str(mapping.get("click", "single")),
        )
        for name, mapping in (raw.get("points") or {}).items()
    }
    if "confirm_yes" not in points:
        legacy = points.pop("yes", None) or points.pop(True, None)
        if legacy is not None:
            points["confirm_yes"] = legacy
        else:
            points["confirm_yes"] = Point(x=880, y=560, click="single")

    sequences = _normalize_sequences(recovery_raw.get("sequences") or {})
    sequences = _migrate_sequence(sequences, recovery_raw)

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
            stop_confirm_wait_sec=float(recovery_raw.get("stop_confirm_wait_sec", 1)),
            editor_managed=bool(recovery_raw.get("editor_managed", False)),
            sequences=sequences,
        ),
        rules=list(raw.get("rules") or []),
    )


def _normalize_point_name(name: Any) -> str:
    # YAML 1.1 treats unquoted yes/on as boolean True.
    if name is True or str(name).lower() in {"yes", "true"}:
        return "confirm_yes"
    return str(name)


def _normalize_sequences(
    sequences: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    normalized: dict[str, list[dict[str, Any]]] = {}
    for name, steps in dict(sequences).items():
        copied: list[dict[str, Any]] = []
        for step in steps or []:
            item = dict(step)
            if "point" in item:
                item["point"] = _normalize_point_name(item["point"])
            copied.append(item)
        normalized[name] = copied
    return normalized


def _ensure_confirm_after(
    sequences: dict[str, list[dict[str, Any]]],
    after_point: str,
) -> dict[str, list[dict[str, Any]]]:
    steps = list(sequences.get("restart_app") or [])
    if not steps:
        return sequences
    after_idx = next(
        (
            index
            for index, step in enumerate(steps)
            if step.get("action") == "click" and step.get("point") == after_point
        ),
        None,
    )
    if after_idx is None:
        return sequences
    next_click = next(
        (
            step.get("point")
            for step in steps[after_idx + 1 :]
            if step.get("action") == "click"
        ),
        None,
    )
    if next_click == "confirm_yes":
        return sequences
    inserted = steps[: after_idx + 1]
    inserted.append({"action": "wait", "from": "stop_confirm_wait_sec"})
    inserted.append({"action": "click", "point": "confirm_yes"})
    inserted.extend(steps[after_idx + 1 :])
    sequences["restart_app"] = inserted
    return sequences


def _migrate_sequence(
    sequences: dict[str, list[dict[str, Any]]],
    recovery_raw: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    editor_managed = bool(recovery_raw.get("editor_managed", False))
    if not editor_managed:
        sequences = _ensure_confirm_after(sequences, "stop")
        sequences = _ensure_confirm_after(sequences, "close")
        sequences = _ensure_shutdown_wait(sequences)
    sequences = _flatten_sequence_waits(sequences, recovery_raw)
    return sequences


def _flatten_sequence_waits(
    sequences: dict[str, list[dict[str, Any]]],
    recovery_raw: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    startup = float(recovery_raw.get("startup_wait_sec", 10))
    confirm = float(recovery_raw.get("stop_confirm_wait_sec", 1))
    steps = list(sequences.get("restart_app") or [])
    flattened: list[dict[str, Any]] = []
    for step in steps:
        item = dict(step)
        if item.get("action") == "wait":
            source = item.get("from")
            if source == "startup_wait_sec":
                item["sec"] = startup
            elif source == "stop_confirm_wait_sec":
                item["sec"] = confirm
            item.setdefault("sec", 1.0)
            item["sec"] = float(item["sec"])
            item.pop("from", None)
        item.setdefault("enabled", True)
        flattened.append(item)
    if steps:
        sequences["restart_app"] = flattened
    return sequences


def _ensure_shutdown_wait(
    sequences: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    steps = list(sequences.get("restart_app") or [])
    icon_idx = next(
        (
            index
            for index, step in enumerate(steps)
            if step.get("action") == "click" and step.get("point") == "launch_icon"
        ),
        None,
    )
    if icon_idx is None:
        return sequences
    if icon_idx > 0 and steps[icon_idx - 1].get("action") == "wait":
        prev = steps[icon_idx - 1]
        sec = prev.get("sec")
        source = prev.get("from")
        if source == "startup_wait_sec":
            return sequences
        if sec in (1, 1.0) or source == "stop_confirm_wait_sec":
            prev = dict(prev)
            prev["sec"] = 5
            prev.pop("from", None)
            steps[icon_idx - 1] = prev
    else:
        steps.insert(icon_idx, {"action": "wait", "sec": 5, "enabled": True})
    sequences["restart_app"] = steps
    return sequences
