"""Tkinter dashboard: monitor, calibrate, dry-run recovery, event log."""

from __future__ import annotations

import logging
import os
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from src.calibrator import POINT_COLORS, run_calibrator
from src.capture import capture_screen
from src.config import AppConfig, ensure_config_file, load_config, save_config
from src.control import ControlEngine
from src.events import EventLog
from src.monitor import Monitor, MonitorTick
from src.ocr_engine import OCREngine
from src.paths import APP_VERSION, app_root, logs_dir
from src.process_editor import ProcessEditorPanel
from src.recovery import (
    build_restart_actions,
    has_enabled_launch_step,
    resolve_launch_path,
    run_sequence,
)


def apply_window_state(window: tk.Misc, state: str) -> str:
    """Minimize to the taskbar, or restore a hidden dashboard."""
    if state == "minimized":
        window.iconify()
        return "minimized"
    window.deiconify()
    try:
        window.lift()
    except tk.TclError:
        pass
    return "normal"


def _rule_threshold(config: AppConfig) -> int:
    for rule in config.rules:
        when = rule.get("when") or {}
        for cond in when.get("all") or when.get("any") or []:
            if cond.get("type") == "ocr_count":
                return int(cond.get("min") or 21)
    return 21


class Dashboard:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = ensure_config_file(config_path)
        self.config = load_config(self.config_path)
        self.event_log = EventLog(logs_dir() / "events.jsonl")
        self._running = False
        self._thread: threading.Thread | None = None
        self._monitor: Monitor | None = None

        self.root = tk.Tk()
        self.root.title(f"NaN Freeze Restart Agent v{APP_VERSION}")
        self.root.geometry("960x720")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.dry_run = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Idle")
        self.count_text = tk.StringVar(value="NaN: -")
        self.confirm_text = tk.StringVar(value="Confirm: 0")
        self.backend_text = tk.StringVar(value="OCR: -")

        self._build()
        self._refresh_preview()

    def _build(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="Start monitor", command=self.start_monitor).pack(side="left", padx=4)
        ttk.Button(top, text="Stop", command=self.stop_monitor).pack(side="left", padx=4)
        ttk.Button(top, text="Calibrate", command=self.open_calibrator).pack(side="left", padx=4)
        ttk.Button(top, text="Dry-run recovery", command=self.dry_run_recovery).pack(
            side="left", padx=4
        )
        ttk.Checkbutton(top, text="Dry-run clicks", variable=self.dry_run).pack(side="left", padx=8)

        info = ttk.Frame(self.root, padding=8)
        info.pack(fill="x")
        ttk.Label(info, textvariable=self.status, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(info, textvariable=self.count_text).pack(anchor="w")
        ttk.Label(info, textvariable=self.confirm_text).pack(anchor="w")
        ttk.Label(info, textvariable=self.backend_text).pack(anchor="w")
        ttk.Label(
            info,
            text="Safety: pyautogui FAILSAFE — slam the mouse into a screen corner to abort clicks.",
        ).pack(anchor="w", pady=(6, 0))

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=8, pady=4)

        monitor = ttk.Frame(notebook)
        notebook.add(monitor, text="Monitor")

        self.preview = tk.Canvas(monitor, height=180, bg="#1a1a1a", highlightthickness=0)
        self.preview.pack(fill="x", padx=4, pady=4)

        ttk.Label(monitor, text="Log").pack(anchor="w", padx=4)
        self.log_widget = tk.Text(monitor, height=16, wrap="word")
        self.log_widget.pack(fill="both", expand=True, padx=4, pady=(0, 8))
        self._append_log("Ready. Calibrate ROI/points, then edit Process Editor waits if needed.")

        editor_tab = ttk.Frame(notebook)
        notebook.add(editor_tab, text="Process Editor")
        self._process_editor = ProcessEditorPanel(
            editor_tab,
            self.config,
            self.config_path,
            on_save=self._on_process_saved,
        )
        self._process_editor.frame.pack(fill="both", expand=True)

    def start_monitor(self) -> None:
        if hasattr(self, "_process_editor"):
            self._apply_process_config(self._process_editor.save())
        else:
            self._apply_process_config(load_config(self.config_path))
        if has_enabled_launch_step(self.config) and not resolve_launch_path(self.config):
            messagebox.showwarning(
                "Launch path required",
                "Process Editor에서 재실행할 .exe 또는 바로가기를 지정하십시오.\n"
                "아이콘 더블클릭 대신 관리자 권한(runas)으로 실행합니다.",
            )
            if not self._running:
                return
        if self._running:
            return
        self._running = True
        self.status.set("Monitoring")
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        self._append_log("Monitor started")
        apply_window_state(self.root, "minimized")

    def stop_monitor(self) -> None:
        self._running = False
        if self._monitor is not None:
            self._monitor.stop()
        self.status.set("Stopped")
        self._append_log("Monitor stopped")

    def open_calibrator(self) -> None:
        if self._running:
            messagebox.showinfo("Busy", "Stop the monitor before calibrating.")
            return
        run_calibrator(
            self.root,
            self.config,
            self.config_path,
            on_save=self._on_calibrated,
        )

    def dry_run_recovery(self) -> None:
        if hasattr(self, "_process_editor"):
            self.config.recovery.launch_path = str(
                self._process_editor._launch_path.get() or ""
            )
            self.config.recovery.sequences["restart_app"] = [
                dict(step) for step in self._process_editor._steps
            ]
        actions = build_restart_actions(self.config)
        log = run_sequence(actions, self.config, control=None, dry_run=True)
        self.event_log.write({"type": "dry_run_recovery", "steps": [a["action"] for a in log]})
        for entry in log:
            self._append_log(f"DRY-RUN {entry}")

    def _on_calibrated(self) -> None:
        save_config(self.config_path, self.config)
        if hasattr(self, "_process_editor"):
            self._process_editor.config = self.config
        self._append_log(f"Calibration saved to {self.config_path}")
        self._refresh_preview()

    def _apply_process_config(self, config: AppConfig) -> None:
        self.config = config
        if self._monitor is not None:
            self._monitor.config = config

    def _on_process_saved(self) -> None:
        self._apply_process_config(self._process_editor.config)
        applied = ""
        if self._monitor is not None:
            applied = "; applied to running monitor"
        self._append_log(
            f"Process sequence saved ({len(self.config.recovery.sequences.get('restart_app') or [])} steps){applied}"
        )

    def _monitor_loop(self) -> None:
        try:
            ocr = OCREngine(backend=self.config.ocr.backend)
            backend = ocr.backend
        except Exception as exc:
            self.root.after(0, self._on_monitor_failed, str(exc))
            return
        self.root.after(0, self.backend_text.set, f"OCR: {backend}")
        control = ControlEngine(self.config.control)
        monitor = Monitor(
            self.config,
            ocr=ocr,
            control=control,
            dry_run=bool(self.dry_run.get()),
            on_event=self._on_event,
        )
        self._monitor = monitor
        interval = float(self.config.monitor.interval_sec)
        while self._running:
            try:
                tick = monitor.tick()
            except Exception as exc:
                self.root.after(0, self._append_log, f"Monitor error: {exc}")
                time.sleep(interval)
                continue
            self.root.after(0, self._apply_tick, tick)
            deadline = time.time() + interval
            while self._running and time.time() < deadline:
                time.sleep(0.1)

    def _on_monitor_failed(self, message: str) -> None:
        self._running = False
        self.status.set("Idle")
        self._append_log(f"OCR init failed: {message}")
        apply_window_state(self.root, "normal")

    def _apply_tick(self, tick: MonitorTick) -> None:
        threshold = _rule_threshold(self.config)
        self.count_text.set(f"NaN: {tick.nan_count} / threshold {threshold}")
        needed = self.config.monitor.confirm_scans
        self.confirm_text.set(f"Confirm: {tick.confirm_hits} / {needed}")
        if tick.triggered:
            self.status.set(f"Recovery: {tick.sequence}")
        elif tick.cooldown_remaining > 0:
            self.status.set(f"Cooldown {tick.cooldown_remaining:.1f}s")
        elif self._running:
            self.status.set("Monitoring")
        preview = " ".join(tick.tokens[:12]) if tick.tokens else "(no OCR text)"
        self._append_log(f"scan nan={tick.nan_count} tokens={preview}")

    def _on_event(self, event: dict) -> None:
        self.event_log.write(event)

    def _refresh_preview(self) -> None:
        self.preview.delete("all")
        width = max(self.preview.winfo_width(), 780)
        height = 180
        try:
            image = capture_screen()
            img_h, img_w = image.shape[:2]
        except Exception:
            img_w, img_h = 1920, 1080
            image = None
        scale = min(width / img_w, height / img_h)
        roi = self.config.rois.get("table")
        if roi is not None:
            self.preview.create_rectangle(
                roi.x * scale,
                roi.y * scale,
                (roi.x + roi.w) * scale,
                (roi.y + roi.h) * scale,
                outline="#00ff88",
                width=2,
            )
            self.preview.create_text(
                roi.x * scale + 4,
                roi.y * scale + 8,
                text="table ROI",
                fill="#00ff88",
                anchor="w",
            )
        for name, point in self.config.points.items():
            color = POINT_COLORS.get(name, "#ffffff")
            cx, cy = point.x * scale, point.y * scale
            self.preview.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=color, outline=color)
            self.preview.create_text(cx + 8, cy, text=name, fill=color, anchor="w")
        if image is None:
            self.preview.create_text(
                10,
                height - 16,
                text="Preview uses config geometry (screen capture unavailable).",
                fill="#aaaaaa",
                anchor="w",
            )

    def _append_log(self, message: str) -> None:
        if not hasattr(self, "log_widget"):
            return
        stamp = time.strftime("%H:%M:%S")
        self.log_widget.insert("end", f"{stamp}  {message}\n")
        self.log_widget.see("end")

    def _on_close(self) -> None:
        self.stop_monitor()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    os.chdir(app_root())
    logs_dir()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(logs_dir() / "agent.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    Dashboard().run()


if __name__ == "__main__":
    main()
