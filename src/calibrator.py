"""Fullscreen overlay to drag the table ROI and click named recovery points."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

from src.config import AppConfig, Point, Roi, save_config

POINT_NAMES = ("stop", "confirm_yes", "close", "launch_icon", "start")
POINT_COLORS = {
    "stop": "#ff5555",
    "confirm_yes": "#ff66cc",
    "close": "#ffaa00",
    "launch_icon": "#55aaff",
    "start": "#55ff88",
}
MODE_LABELS = {
    "roi": "ROI (drag table region)",
    "stop": "STOP button",
    "confirm_yes": "Yes (popup)",
    "close": "Close / X button",
    "launch_icon": "Launch icon",
    "start": "START button",
}


def apply_roi(config: AppConfig, name: str, x1: int, y1: int, x2: int, y2: int) -> Roi:
    left, top = min(x1, x2), min(y1, y2)
    width, height = abs(x2 - x1), abs(y2 - y1)
    roi = Roi(x=int(left), y=int(top), w=int(width), h=int(height))
    config.rois[name] = roi
    return roi


def apply_point(
    config: AppConfig,
    name: str,
    x: int,
    y: int,
    click: Optional[str] = None,
) -> Point:
    existing = config.points.get(name)
    click_type = click or (existing.click if existing is not None else "single")
    point = Point(x=int(x), y=int(y), click=click_type)
    config.points[name] = point
    return point


def run_calibrator(
    parent: tk.Misc | None,
    config: AppConfig,
    config_path: str | Path,
    on_save: Optional[Callable[[], None]] = None,
) -> None:
    overlay = CalibratorOverlay(parent, config, Path(config_path), on_save=on_save)
    overlay.show()


class CalibratorOverlay:
    def __init__(
        self,
        parent: tk.Misc | None,
        config: AppConfig,
        config_path: Path,
        on_save: Optional[Callable[[], None]] = None,
    ) -> None:
        self.config = config
        self.config_path = config_path
        self.on_save = on_save
        self.mode = "roi"
        self._drag_start: tuple[int, int] | None = None
        self._drag_rect = None
        self._window = tk.Toplevel(parent) if parent is not None else tk.Tk()
        self._owns_mainloop = parent is None
        self._status = tk.StringVar()
        self._build()

    def show(self) -> None:
        if self._owns_mainloop:
            self._window.mainloop()
        else:
            self._window.grab_set()
            self._window.focus_force()

    def _build(self) -> None:
        win = self._window
        win.title("Calibrate ROI and click points")
        win.attributes("-fullscreen", True)
        win.attributes("-topmost", True)
        try:
            win.attributes("-alpha", 0.42)
        except tk.TclError:
            pass
        win.configure(bg="#111111")
        win.bind("<Escape>", lambda _e: self._close())
        win.bind("<Return>", lambda _e: self._save())
        win.bind("r", lambda _e: self._set_mode("roi"))
        win.bind("s", lambda _e: self._set_mode("stop"))
        win.bind("y", lambda _e: self._set_mode("confirm_yes"))
        win.bind("x", lambda _e: self._set_mode("close"))
        win.bind("i", lambda _e: self._set_mode("launch_icon"))
        win.bind("t", lambda _e: self._set_mode("start"))

        bar = tk.Frame(win, bg="#222222")
        bar.pack(fill="x")
        tk.Label(
            bar,
            text="Calibrate: drag ROI or click a point. Enter=Save  Esc=Close",
            fg="white",
            bg="#222222",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left", padx=8, pady=6)
        for mode in ("roi",) + POINT_NAMES:
            tk.Button(
                bar,
                text=MODE_LABELS[mode],
                command=lambda m=mode: self._set_mode(m),
            ).pack(side="left", padx=4, pady=4)
        tk.Button(bar, text="Save", command=self._save).pack(side="right", padx=8)
        tk.Button(bar, text="Close", command=self._close).pack(side="right")
        tk.Label(bar, textvariable=self._status, fg="#ffffaa", bg="#222222").pack(
            side="right", padx=12
        )

        self.canvas = tk.Canvas(win, bg="#111111", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Map>", lambda _e: self._redraw())
        self.canvas.bind("<Configure>", lambda _e: self._redraw())
        self._set_mode("roi")
        self._redraw()

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self._status.set(f"Mode: {MODE_LABELS[mode]}")
        self._redraw()

    def _on_press(self, event: tk.Event) -> None:
        if self.mode == "roi":
            self._drag_start = (event.x_root, event.y_root)
            self._drag_rect = self.canvas.create_rectangle(
                event.x, event.y, event.x, event.y, outline="#00ff88", width=2, tags="mark"
            )
            return
        apply_point(self.config, self.mode, event.x_root, event.y_root)
        self._status.set(f"{self.mode} = ({event.x_root}, {event.y_root})")
        self._redraw()

    def _on_drag(self, event: tk.Event) -> None:
        if self.mode != "roi" or self._drag_rect is None or self._drag_start is None:
            return
        x0 = self._drag_start[0] - self.canvas.winfo_rootx()
        y0 = self._drag_start[1] - self.canvas.winfo_rooty()
        self.canvas.coords(self._drag_rect, x0, y0, event.x, event.y)

    def _on_release(self, event: tk.Event) -> None:
        if self.mode != "roi" or self._drag_start is None:
            return
        x1, y1 = self._drag_start
        apply_roi(self.config, "table", x1, y1, event.x_root, event.y_root)
        self._drag_start = None
        self._drag_rect = None
        roi = self.config.rois["table"]
        self._status.set(f"table ROI = {roi.as_xywh()}")
        self._redraw()

    def _redraw(self) -> None:
        self.canvas.delete("mark")
        origin_x = self.canvas.winfo_rootx()
        origin_y = self.canvas.winfo_rooty()
        roi = self.config.rois.get("table")
        if roi is not None and roi.w > 0 and roi.h > 0:
            self.canvas.create_rectangle(
                roi.x - origin_x,
                roi.y - origin_y,
                roi.x + roi.w - origin_x,
                roi.y + roi.h - origin_y,
                outline="#00ff88",
                width=3,
                tags="mark",
            )
            self.canvas.create_text(
                roi.x - origin_x + 8,
                roi.y - origin_y + 12,
                text="table ROI",
                fill="#00ff88",
                anchor="w",
                tags="mark",
            )
        for name, point in self.config.points.items():
            color = POINT_COLORS.get(name, "#ffffff")
            cx, cy = point.x - origin_x, point.y - origin_y
            self.canvas.create_oval(cx - 8, cy - 8, cx + 8, cy + 8, outline=color, width=2, tags="mark")
            self.canvas.create_text(
                cx + 12,
                cy,
                text=f"{name} ({point.x},{point.y})",
                fill=color,
                anchor="w",
                tags="mark",
            )

    def _save(self) -> None:
        save_config(self.config_path, self.config)
        self._status.set(f"Saved {self.config_path}")
        if self.on_save is not None:
            self.on_save()

    def _close(self) -> None:
        try:
            self._window.grab_release()
        except tk.TclError:
            pass
        self._window.destroy()
