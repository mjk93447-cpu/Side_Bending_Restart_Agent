"""Build and run calibrated recovery click sequences."""

from __future__ import annotations

import logging
from typing import Any

from src.config import AppConfig

logger = logging.getLogger(__name__)


def build_restart_actions(
    config: AppConfig,
    sequence_name: str = "restart_app",
) -> list[dict[str, Any]]:
    raw_steps = config.recovery.sequences.get(sequence_name) or []
    actions: list[dict[str, Any]] = []
    for step in raw_steps:
        action = dict(step)
        if action.get("action") == "wait":
            source = action.get("from")
            if source == "startup_wait_sec":
                action["sec"] = float(config.recovery.startup_wait_sec)
            elif source == "stop_confirm_wait_sec":
                action["sec"] = float(config.recovery.stop_confirm_wait_sec)
        if action.get("action") == "click":
            point_name = action.get("point")
            if not point_name or point_name not in config.points:
                raise KeyError(f"Unknown recovery point: {point_name!r}")
            point = config.points[point_name]
            action["x"] = point.x
            action["y"] = point.y
            action["click"] = point.click
        actions.append(action)
    return actions


def run_sequence(
    actions: list[dict[str, Any]],
    config: AppConfig,
    control: Any,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    log: list[dict[str, Any]] = []
    for action in actions:
        entry = dict(action)
        entry["dry_run"] = dry_run
        kind = action.get("action")
        if dry_run:
            logger.info("DRY-RUN %s", entry)
        elif kind == "wait":
            control.wait(action.get("sec", 0))
        elif kind == "click":
            click_type = action.get("click", "single")
            x, y = int(action["x"]), int(action["y"])
            if click_type == "double":
                control.double_click_at(x, y)
            else:
                control.click_at(x, y)
        else:
            raise ValueError(f"Unsupported recovery action: {kind!r}")
        log.append(entry)
    return log
