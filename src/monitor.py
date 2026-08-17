"""Capture → OCR count → AND/OR rules → recovery sequence."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from src.capture import capture_screen
from src.conditions import ConditionContext, evaluate_rules
from src.config import AppConfig
from src.nan_counter import count_nan_in_image
from src.recovery import build_restart_actions, run_sequence

logger = logging.getLogger(__name__)


@dataclass
class MonitorTick:
    nan_count: int
    triggered: bool
    sequence: Optional[str]
    confirm_hits: int
    recovering: bool
    cooldown_remaining: float
    tokens: list[str]


class Monitor:
    def __init__(
        self,
        config: AppConfig,
        ocr: Any,
        control: Any,
        dry_run: bool = False,
        on_event: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> None:
        self.config = config
        self.ocr = ocr
        self.control = control
        self.dry_run = dry_run
        self.on_event = on_event
        self.confirm_hits = 0
        self.last_recovery_at: Optional[float] = None
        self.recovering = False
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True

    def tick(self, now: Optional[float] = None) -> MonitorTick:
        image = capture_screen()
        return self.process_frame(image, now=now)

    def process_frame(self, image: Any, now: Optional[float] = None) -> MonitorTick:
        now = time.time() if now is None else now
        roi = self.config.rois["table"].as_xywh() if "table" in self.config.rois else None
        n0n = self.config.ocr.n0n_correction
        count, regions = count_nan_in_image(
            image,
            self.ocr,
            roi=roi,
            n0n_correction=n0n,
        )
        tokens = [r.text for r in regions[:40]]
        remaining = self._cooldown_remaining(now)

        if self.stopped or remaining > 0:
            self._emit(
                {
                    "type": "scan",
                    "nan_count": count,
                    "triggered": False,
                    "cooldown_remaining": remaining,
                }
            )
            return MonitorTick(
                nan_count=count,
                triggered=False,
                sequence=None,
                confirm_hits=self.confirm_hits,
                recovering=self.recovering,
                cooldown_remaining=remaining,
                tokens=tokens,
            )

        ctx = ConditionContext(
            nan_counts={"table": count},
            regions={"table": regions},
            config=self.config,
        )
        matched = evaluate_rules(self.config.rules, ctx)
        if matched:
            self.confirm_hits += 1
        else:
            self.confirm_hits = 0

        triggered = bool(
            matched and self.confirm_hits >= int(self.config.monitor.confirm_scans)
        )
        sequence = None
        if triggered:
            sequence = matched
            self.confirm_hits = 0
            self.last_recovery_at = now
            self.recovering = True
            self._emit(
                {
                    "type": "recovery_start",
                    "sequence": sequence,
                    "nan_count": count,
                    "dry_run": self.dry_run,
                }
            )
            try:
                actions = build_restart_actions(self.config, sequence_name=sequence)
                run_sequence(actions, self.config, self.control, dry_run=self.dry_run)
            finally:
                self.recovering = False
            self._emit({"type": "recovery_done", "sequence": sequence})

        self._emit(
            {
                "type": "scan",
                "nan_count": count,
                "triggered": triggered,
                "confirm_hits": self.confirm_hits,
            }
        )
        return MonitorTick(
            nan_count=count,
            triggered=triggered,
            sequence=sequence,
            confirm_hits=self.confirm_hits,
            recovering=self.recovering,
            cooldown_remaining=self._cooldown_remaining(now),
            tokens=tokens,
        )

    def _cooldown_remaining(self, now: float) -> float:
        if self.last_recovery_at is None:
            return 0.0
        elapsed = now - self.last_recovery_at
        remaining = float(self.config.monitor.cooldown_sec) - elapsed
        return remaining if remaining > 0 else 0.0

    def _emit(self, event: dict[str, Any]) -> None:
        logger.info("%s", event)
        if self.on_event is not None:
            self.on_event(event)
