"""Edit recovery click/wait steps. Logic is UI-independent; Tk panel is optional."""

from __future__ import annotations

from typing import Any, Callable, Optional

from src.config import AppConfig, load_config, save_config


def flatten_wait_step(
    step: dict[str, Any],
    startup_wait_sec: float = 10.0,
    stop_confirm_wait_sec: float = 1.0,
) -> dict[str, Any]:
    item = dict(step)
    if item.get("action") != "wait":
        item.setdefault("enabled", True)
        return item
    source = item.get("from")
    if source == "startup_wait_sec":
        item["sec"] = float(startup_wait_sec)
    elif source == "stop_confirm_wait_sec":
        item["sec"] = float(stop_confirm_wait_sec)
    item.setdefault("sec", 1.0)
    item["sec"] = float(item["sec"])
    item.pop("from", None)
    item.setdefault("enabled", True)
    return item


def enabled_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(step) for step in steps if step.get("enabled", True)]


def new_click_step(point: str, enabled: bool = True) -> dict[str, Any]:
    return {"action": "click", "point": str(point), "enabled": bool(enabled)}


def new_wait_step(sec: float, enabled: bool = True) -> dict[str, Any]:
    return {"action": "wait", "sec": float(sec), "enabled": bool(enabled)}


def insert_step(
    steps: list[dict[str, Any]],
    index: int,
    step: dict[str, Any],
) -> list[dict[str, Any]]:
    out = [dict(item) for item in steps]
    index = max(0, min(int(index), len(out)))
    out.insert(index, dict(step))
    return out


def delete_step(steps: list[dict[str, Any]], index: int) -> list[dict[str, Any]]:
    out = [dict(item) for item in steps]
    if 0 <= index < len(out):
        out.pop(index)
    return out


def move_step(
    steps: list[dict[str, Any]],
    index: int,
    delta: int,
) -> list[dict[str, Any]]:
    out = [dict(item) for item in steps]
    dest = index + delta
    if not (0 <= index < len(out) and 0 <= dest < len(out)):
        return out
    out[index], out[dest] = out[dest], out[index]
    return out


def set_step_enabled(
    steps: list[dict[str, Any]],
    index: int,
    enabled: bool,
) -> list[dict[str, Any]]:
    out = [dict(item) for item in steps]
    if 0 <= index < len(out):
        out[index]["enabled"] = bool(enabled)
    return out


def set_wait_seconds(
    steps: list[dict[str, Any]],
    index: int,
    sec: float,
) -> list[dict[str, Any]]:
    out = [dict(item) for item in steps]
    if 0 <= index < len(out):
        value = max(0.1, min(180.0, float(sec)))
        out[index]["action"] = "wait"
        out[index]["sec"] = value
        out[index].pop("from", None)
        out[index].setdefault("enabled", True)
    return out


def describe_step(step: dict[str, Any]) -> str:
    if step.get("action") == "wait":
        return f"Wait {float(step.get('sec', 0)):g}s"
    point = step.get("point", "?")
    return f"Click {point}"


def save_process_steps(config_path: Any, steps: list[dict[str, Any]]) -> AppConfig:
    """Write sequence edits onto the latest yaml so calibration is not overwritten."""
    latest = load_config(config_path)
    latest.recovery.sequences["restart_app"] = [dict(step) for step in steps]
    latest.recovery.editor_managed = True
    save_config(config_path, latest)
    return latest


class ProcessEditorPanel:
    """Tk table editor modeled on SOP agent's SOP Edit tab."""

    def __init__(
        self,
        parent: Any,
        config: AppConfig,
        config_path: Any,
        on_save: Optional[Callable[[], None]] = None,
    ) -> None:
        import tkinter as tk
        from tkinter import messagebox, ttk

        self.config = config
        self.config_path = config_path
        self.on_save = on_save
        self._steps = [
            dict(step) for step in (config.recovery.sequences.get("restart_app") or [])
        ]
        self._tk = tk
        self._ttk = ttk
        self._messagebox = messagebox
        self.frame = ttk.Frame(parent, padding=8)
        self._status = tk.StringVar(value="")
        self._build()
        self.refresh()

    def _build(self) -> None:
        tk = self._tk
        ttk = self._ttk
        header = ttk.Label(
            self.frame,
            text="Process Editor — recovery click / wait steps",
            font=("Segoe UI", 12, "bold"),
        )
        header.pack(anchor="w")
        ttk.Label(
            self.frame,
            text="Add, exclude, delete, or change wait seconds. Save writes config.yaml.",
        ).pack(anchor="w", pady=(0, 6))

        columns = ("on", "n", "action", "detail", "param")
        self._tree = ttk.Treeview(
            self.frame, columns=columns, show="headings", height=14, selectmode="browse"
        )
        self._tree.heading("on", text="On")
        self._tree.heading("n", text="#")
        self._tree.heading("action", text="Type")
        self._tree.heading("detail", text="Target / wait")
        self._tree.heading("param", text="sec / click")
        self._tree.column("on", width=50, anchor="center")
        self._tree.column("n", width=40, anchor="center")
        self._tree.column("action", width=80, anchor="center")
        self._tree.column("detail", width=280, anchor="w")
        self._tree.column("param", width=120, anchor="center")
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<Double-1>", lambda _e: self._on_edit())

        buttons = ttk.Frame(self.frame)
        buttons.pack(fill="x", pady=8)
        ttk.Button(buttons, text="Add click", command=self._on_add_click).pack(
            side="left", padx=2
        )
        ttk.Button(buttons, text="Add wait", command=self._on_add_wait).pack(
            side="left", padx=2
        )
        ttk.Button(buttons, text="Edit", command=self._on_edit).pack(side="left", padx=2)
        ttk.Button(buttons, text="Exclude / Include", command=self._on_toggle).pack(
            side="left", padx=2
        )
        ttk.Button(buttons, text="Delete", command=self._on_delete).pack(
            side="left", padx=2
        )
        ttk.Button(buttons, text="Move up", command=lambda: self._on_move(-1)).pack(
            side="left", padx=2
        )
        ttk.Button(buttons, text="Move down", command=lambda: self._on_move(1)).pack(
            side="left", padx=2
        )
        ttk.Button(buttons, text="Save", command=self.save).pack(side="right", padx=2)

        ttk.Label(self.frame, textvariable=self._status).pack(anchor="w")

    def set_config(self, config: AppConfig) -> None:
        self.config = config
        self._steps = [
            dict(step) for step in (config.recovery.sequences.get("restart_app") or [])
        ]
        self.refresh()

    def refresh(self) -> None:
        tree = self._tree
        for item in tree.get_children():
            tree.delete(item)
        for index, step in enumerate(self._steps):
            enabled = step.get("enabled", True)
            if step.get("action") == "wait":
                detail = describe_step(step)
                param = f"{float(step.get('sec', 0)):g}s"
            else:
                detail = describe_step(step)
                point = self.config.points.get(str(step.get("point") or ""))
                param = point.click if point is not None else ""
            tree.insert(
                "",
                "end",
                iid=str(index),
                values=("ON" if enabled else "OFF", index + 1, step.get("action"), detail, param),
                tags=("off",) if not enabled else (),
            )
        tree.tag_configure("off", foreground="#888888")

    def _selected_index(self) -> int:
        selected = self._tree.selection()
        if not selected:
            return -1
        return int(selected[0])

    def _on_add_click(self) -> None:
        names = list(self.config.points.keys())
        if not names:
            self._messagebox.showwarning("No points", "Calibrate click points first.")
            return
        step = self._edit_dialog(new_click_step(names[0]))
        if step is None:
            return
        index = self._selected_index()
        insert_at = index + 1 if index >= 0 else len(self._steps)
        self._steps = insert_step(self._steps, insert_at, step)
        self.refresh()

    def _on_add_wait(self) -> None:
        step = self._edit_dialog(new_wait_step(1.0))
        if step is None:
            return
        index = self._selected_index()
        insert_at = index + 1 if index >= 0 else len(self._steps)
        self._steps = insert_step(self._steps, insert_at, step)
        self.refresh()

    def _on_edit(self) -> None:
        index = self._selected_index()
        if index < 0:
            return
        step = self._edit_dialog(dict(self._steps[index]))
        if step is None:
            return
        self._steps[index] = step
        self.refresh()

    def _on_toggle(self) -> None:
        index = self._selected_index()
        if index < 0:
            return
        current = bool(self._steps[index].get("enabled", True))
        self._steps = set_step_enabled(self._steps, index, not current)
        self.refresh()
        self._tree.selection_set(str(index))

    def _on_delete(self) -> None:
        index = self._selected_index()
        if index < 0:
            return
        name = describe_step(self._steps[index])
        if not self._messagebox.askyesno("Delete step", f"Delete '{name}'?"):
            return
        self._steps = delete_step(self._steps, index)
        self.refresh()

    def _on_move(self, delta: int) -> None:
        index = self._selected_index()
        if index < 0:
            return
        self._steps = move_step(self._steps, index, delta)
        self.refresh()
        dest = index + delta
        if 0 <= dest < len(self._steps):
            self._tree.selection_set(str(dest))

    def save(self) -> AppConfig:
        latest = save_process_steps(self.config_path, self._steps)
        self.config = latest
        self._status.set(f"Saved {len(self._steps)} steps to {self.config_path}")
        if self.on_save is not None:
            self.on_save()
        return latest

    def _edit_dialog(self, step: dict[str, Any]) -> Optional[dict[str, Any]]:
        tk = self._tk
        ttk = self._ttk
        dialog = tk.Toplevel(self.frame)
        dialog.title("Edit step")
        dialog.transient(self.frame.winfo_toplevel())
        dialog.grab_set()
        result: dict[str, Any] = {}

        kind = tk.StringVar(value=str(step.get("action") or "click"))
        point = tk.StringVar(value=str(step.get("point") or next(iter(self.config.points), "stop")))
        wait = tk.DoubleVar(value=float(step.get("sec") or 1.0))
        enabled = tk.BooleanVar(value=bool(step.get("enabled", True)))

        form = ttk.Frame(dialog, padding=10)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Type").grid(row=0, column=0, sticky="w", pady=4)
        kind_combo = ttk.Combobox(
            form, textvariable=kind, values=("click", "wait"), state="readonly", width=16
        )
        kind_combo.grid(row=0, column=1, sticky="w")
        kind_combo.set(kind.get())
        ttk.Label(form, text="Click point").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(
            form,
            textvariable=point,
            values=list(self.config.points.keys()),
            state="readonly",
            width=16,
        ).grid(row=1, column=1, sticky="w")
        ttk.Label(form, text="Wait (sec)").grid(row=2, column=0, sticky="w", pady=4)
        wait_spin = ttk.Spinbox(
            form, from_=0.0, to=180, increment=0.5, textvariable=wait, width=10
        )
        wait_spin.grid(row=2, column=1, sticky="w")
        ttk.Checkbutton(form, text="Enabled (uncheck to exclude)", variable=enabled).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=6
        )

        def accept() -> None:
            try:
                wait_sec = float(wait_spin.get())
            except (TypeError, ValueError):
                wait_sec = float(wait.get())
            if kind.get() == "wait":
                result["step"] = new_wait_step(wait_sec, enabled=bool(enabled.get()))
            else:
                result["step"] = new_click_step(point.get(), enabled=bool(enabled.get()))
            dialog.destroy()

        def cancel() -> None:
            dialog.destroy()

        row = ttk.Frame(form)
        row.grid(row=4, column=0, columnspan=2, pady=8)
        ttk.Button(row, text="OK", command=accept).pack(side="left", padx=4)
        ttk.Button(row, text="Cancel", command=cancel).pack(side="left", padx=4)
        dialog.wait_window()
        return result.get("step")
