"""Dashboard window state: minimize when monitoring starts."""

from pathlib import Path

import src.app as app_mod
from src.app import apply_window_state


class FakeWindow:
    def __init__(self) -> None:
        self.state = "normal"
        self.lifted = False

    def iconify(self) -> None:
        self.state = "iconic"

    def deiconify(self) -> None:
        self.state = "normal"

    def lift(self) -> None:
        self.lifted = True


def test_apply_window_state_minimizes() -> None:
    win = FakeWindow()
    assert apply_window_state(win, "minimized") == "minimized"
    assert win.state == "iconic"


def test_apply_window_state_restores() -> None:
    win = FakeWindow()
    apply_window_state(win, "minimized")
    assert apply_window_state(win, "normal") == "normal"
    assert win.state == "normal"
    assert win.lifted is True


def test_start_monitor_minimizes_dashboard(tmp_path: Path, monkeypatch) -> None:
    dest = tmp_path / "config.yaml"
    dest.write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    dash = app_mod.Dashboard(config_path=dest)
    dash.root.withdraw()
    calls: list[tuple[object, str]] = []

    def fake_apply(window, state: str) -> str:
        calls.append((window, state))
        return state

    class FakeThread:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def start(self) -> None:
            pass

    monkeypatch.setattr(app_mod, "apply_window_state", fake_apply)
    monkeypatch.setattr(app_mod.threading, "Thread", FakeThread)
    try:
        dash.start_monitor()
        assert calls == [(dash.root, "minimized")]
        assert dash._running is True
    finally:
        dash._running = False
        dash.root.destroy()


def test_start_monitor_skips_minimize_when_already_running(
    tmp_path: Path, monkeypatch
) -> None:
    dest = tmp_path / "config.yaml"
    dest.write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    dash = app_mod.Dashboard(config_path=dest)
    dash.root.withdraw()
    dash._running = True
    calls: list[tuple[object, str]] = []
    monkeypatch.setattr(
        app_mod, "apply_window_state", lambda window, state: calls.append((window, state))
    )
    try:
        dash.start_monitor()
        assert calls == []
    finally:
        dash._running = False
        dash.root.destroy()
