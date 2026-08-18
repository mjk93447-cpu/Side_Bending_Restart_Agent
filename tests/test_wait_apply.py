"""Verify Process Editor wait edits are saved and used by recovery."""

from pathlib import Path
import time
import tkinter as tk
from tkinter import ttk

import src.app as app_mod
from src.config import load_config
from src.monitor import Monitor
from src.process_editor import save_process_steps, set_wait_seconds
from src.recovery import build_restart_actions, run_sequence


def _copy_config(tmp_path: Path) -> Path:
    dest = tmp_path / "config.yaml"
    dest.write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def _startup_wait_index(steps: list[dict]) -> int:
    for index, step in enumerate(steps):
        if step.get("point") == "launch_icon":
            return index + 1
    raise AssertionError("launch_icon step missing")


class RecordingControl:
    def __init__(self, sleep: bool = False) -> None:
        self.calls: list[tuple] = []
        self.sleep = sleep

    def click_at(self, x, y):
        self.calls.append(("click", x, y))

    def double_click_at(self, x, y):
        self.calls.append(("double", x, y))

    def wait(self, sec):
        self.calls.append(("wait", float(sec)))
        if self.sleep:
            time.sleep(float(sec))


def _walk(widget: tk.Misc):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _find_spinbox(root: tk.Misc) -> tk.Misc | None:
    for widget in _walk(root):
        if isinstance(widget, (tk.Spinbox, ttk.Spinbox)):
            return widget
    return None


def _find_button(root: tk.Misc, text: str) -> tk.Misc | None:
    for widget in _walk(root):
        if isinstance(widget, (tk.Button, ttk.Button)) and str(widget.cget("text")) == text:
            return widget
    return None


def test_saved_15s_wait_is_used_by_recovery(tmp_path: Path) -> None:
    dest = _copy_config(tmp_path)
    cfg = load_config(dest)
    idx = _startup_wait_index(cfg.recovery.sequences["restart_app"])
    steps = set_wait_seconds(cfg.recovery.sequences["restart_app"], idx, 15)
    save_process_steps(dest, steps)

    reloaded = load_config(dest)
    assert reloaded.recovery.sequences["restart_app"][idx]["sec"] == 15
    actions = build_restart_actions(reloaded)
    control = RecordingControl(sleep=False)
    run_sequence(actions, reloaded, control=control, dry_run=False)
    assert ("wait", 15.0) in control.calls
    icon_at = next(i for i, a in enumerate(actions) if a.get("point") == "launch_icon")
    assert actions[icon_at + 1]["sec"] == 15


def test_dashboard_save_applies_15s_wait(tmp_path: Path, monkeypatch) -> None:
    dest = _copy_config(tmp_path)
    dash = app_mod.Dashboard(config_path=dest)
    dash.root.withdraw()

    class FakeThread:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def start(self) -> None:
            pass

    monkeypatch.setattr(app_mod.threading, "Thread", FakeThread)
    monkeypatch.setattr(app_mod, "apply_window_state", lambda *_a, **_k: "minimized")
    try:
        idx = _startup_wait_index(dash._process_editor._steps)
        dash._process_editor._steps = set_wait_seconds(dash._process_editor._steps, idx, 15)
        dash._process_editor.refresh()
        dash.start_monitor()
        assert dash.config.recovery.sequences["restart_app"][idx]["sec"] == 15
        actions = build_restart_actions(dash.config)
        control = RecordingControl()
        run_sequence(actions, dash.config, control=control, dry_run=False)
        assert ("wait", 15.0) in control.calls
        yaml_text = dest.read_text(encoding="utf-8")
        assert "sec: 15" in yaml_text
    finally:
        dash._running = False
        dash.root.destroy()


def test_edit_dialog_reads_spinbox_value_not_stale_var(tmp_path: Path) -> None:
    dest = _copy_config(tmp_path)
    dash = app_mod.Dashboard(config_path=dest)
    dash.root.withdraw()
    editor = dash._process_editor
    idx = _startup_wait_index(editor._steps)
    editor._tree.selection_set(str(idx))
    found = {"ok": False}

    def fill_and_ok() -> None:
        spin = _find_spinbox(dash.root)
        ok = _find_button(dash.root, "OK")
        if spin is None or ok is None:
            dash.root.after(50, fill_and_ok)
            return
        spin.delete(0, "end")
        spin.insert(0, "15")
        found["ok"] = True
        ok.invoke()

    def abort() -> None:
        for widget in list(_walk(dash.root)):
            if isinstance(widget, tk.Toplevel):
                widget.destroy()

    dash.root.after(100, fill_and_ok)
    dash.root.after(4000, abort)
    editor._on_edit()
    try:
        assert found["ok"] is True
        assert editor._steps[idx]["action"] == "wait"
        assert float(editor._steps[idx]["sec"]) == 15
    finally:
        dash.root.destroy()


def test_process_save_updates_running_monitor_waits(tmp_path: Path, monkeypatch) -> None:
    dest = _copy_config(tmp_path)
    dash = app_mod.Dashboard(config_path=dest)
    dash.root.withdraw()

    class FakeThread:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def start(self) -> None:
            pass

    monkeypatch.setattr(app_mod.threading, "Thread", FakeThread)
    monkeypatch.setattr(app_mod, "apply_window_state", lambda *_a, **_k: "minimized")
    try:
        dash.start_monitor()
        dash._monitor = Monitor(
            dash.config,
            ocr=object(),
            control=RecordingControl(),
            dry_run=True,
        )
        idx = _startup_wait_index(dash._process_editor._steps)
        assert float(dash._monitor.config.recovery.sequences["restart_app"][idx]["sec"]) == 10
        dash._process_editor._steps = set_wait_seconds(dash._process_editor._steps, idx, 15)
        dash._process_editor.save()
        actions = build_restart_actions(dash._monitor.config)
        icon_at = next(i for i, a in enumerate(actions) if a.get("point") == "launch_icon")
        assert actions[icon_at + 1]["sec"] == 15
    finally:
        dash._running = False
        dash.root.destroy()


def test_start_monitor_while_running_applies_new_wait(tmp_path: Path, monkeypatch) -> None:
    dest = _copy_config(tmp_path)
    dash = app_mod.Dashboard(config_path=dest)
    dash.root.withdraw()

    class FakeThread:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def start(self) -> None:
            pass

    monkeypatch.setattr(app_mod.threading, "Thread", FakeThread)
    monkeypatch.setattr(app_mod, "apply_window_state", lambda *_a, **_k: "minimized")
    try:
        dash.start_monitor()
        dash._monitor = Monitor(
            dash.config,
            ocr=object(),
            control=RecordingControl(),
            dry_run=True,
        )
        idx = _startup_wait_index(dash._process_editor._steps)
        dash._process_editor._steps = set_wait_seconds(dash._process_editor._steps, idx, 15)
        dash.start_monitor()
        assert dash._running is True
        actions = build_restart_actions(dash._monitor.config)
        icon_at = next(i for i, a in enumerate(actions) if a.get("point") == "launch_icon")
        assert actions[icon_at + 1]["sec"] == 15
        yaml_text = dest.read_text(encoding="utf-8")
        assert "sec: 15" in yaml_text
    finally:
        dash._running = False
        dash.root.destroy()


def test_live_recovery_sleeps_the_saved_15s_wait(tmp_path: Path) -> None:
    dest = _copy_config(tmp_path)
    cfg = load_config(dest)
    idx = _startup_wait_index(cfg.recovery.sequences["restart_app"])
    save_process_steps(dest, set_wait_seconds(cfg.recovery.sequences["restart_app"], idx, 15))
    reloaded = load_config(dest)
    actions = build_restart_actions(reloaded)
    # Only the edited startup wait should sleep; keep the run short.
    startup = actions[idx]
    assert startup["action"] == "wait"
    assert float(startup["sec"]) == 15
    control = RecordingControl(sleep=True)
    started = time.perf_counter()
    run_sequence([startup], reloaded, control=control, dry_run=False)
    elapsed = time.perf_counter() - started
    assert control.calls == [("wait", 15.0)]
    assert elapsed >= 14.5
    assert elapsed < 17.0
