"""Launch the line app with administrator rights instead of icon double-click."""

from pathlib import Path

from src.config import load_config, save_config
from src.control import ControlEngine, ControlResult
from src.config import ControlConfig
from src.process_editor import describe_step, new_launch_step, save_process_steps
from src.recovery import build_restart_actions, resolve_launch_path, run_sequence


def test_launch_as_admin_calls_shell_execute_runas(tmp_path: Path, monkeypatch) -> None:
    exe = tmp_path / "line_app.exe"
    exe.write_bytes(b"MZ")
    calls: list[tuple] = []

    def fake_runas(path: str, arguments: str = "") -> int:
        calls.append((path, arguments))
        return 42

    monkeypatch.setattr("src.control.shell_execute_runas", fake_runas)
    engine = ControlEngine(ControlConfig(click_pause=0.0))
    result = engine.launch_as_admin(str(exe), "")
    assert result.success is True
    assert calls == [(str(exe), "")]


def test_launch_as_admin_rejects_empty_and_missing_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("src.control.shell_execute_runas", lambda *_a, **_k: 42)
    engine = ControlEngine(ControlConfig(click_pause=0.0))
    empty = engine.launch_as_admin("  ")
    assert empty.success is False
    missing = engine.launch_as_admin(str(tmp_path / "nope.exe"))
    assert missing.success is False


def test_default_sequence_launches_as_admin_not_icon_double_click() -> None:
    cfg = load_config()
    actions = build_restart_actions(cfg)
    kinds = [a["action"] for a in actions]
    assert "launch" in kinds
    assert not any(a.get("point") == "launch_icon" for a in actions)
    launch = next(a for a in actions if a["action"] == "launch")
    assert launch.get("as_admin") is True


def test_old_launch_icon_click_migrates_to_admin_launch(tmp_path: Path) -> None:
    dest = tmp_path / "config.yaml"
    dest.write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    cfg = load_config(dest)
    cfg.recovery.sequences["restart_app"] = [
        {"action": "click", "point": "stop", "enabled": True},
        {"action": "wait", "sec": 5, "enabled": True},
        {"action": "click", "point": "launch_icon", "enabled": True},
        {"action": "wait", "sec": 10, "enabled": True},
        {"action": "click", "point": "start", "enabled": True},
    ]
    save_config(dest, cfg)
    reloaded = load_config(dest)
    actions = build_restart_actions(reloaded)
    assert [a["action"] for a in actions] == ["click", "wait", "launch", "wait", "click"]
    assert actions[2]["as_admin"] is True
    assert actions[-1]["point"] == "start"


def test_run_sequence_dispatches_launch_as_admin(tmp_path: Path) -> None:
    dest = tmp_path / "config.yaml"
    dest.write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    exe = tmp_path / "line_app.exe"
    exe.write_bytes(b"MZ")
    cfg = load_config(dest)
    cfg.recovery.launch_path = str(exe)
    save_config(dest, cfg)
    cfg = load_config(dest)
    actions = build_restart_actions(cfg)
    calls: list[tuple] = []

    class FakeControl:
        def click_at(self, x, y):
            calls.append(("click", x, y))

        def double_click_at(self, x, y):
            calls.append(("double", x, y))

        def wait(self, sec):
            calls.append(("wait", sec))

        def launch_as_admin(self, path, arguments=""):
            calls.append(("launch_admin", path, arguments))
            return ControlResult(True, None, 0.0)

    run_sequence(actions, cfg, control=FakeControl(), dry_run=False)
    assert any(c[0] == "launch_admin" for c in calls)
    launch = next(c for c in calls if c[0] == "launch_admin")
    assert launch[1] == str(exe)
    assert not any(c[0] == "double" for c in calls)


def test_run_sequence_stops_if_admin_launch_fails(tmp_path: Path) -> None:
    dest = tmp_path / "config.yaml"
    dest.write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    exe = tmp_path / "line_app.exe"
    exe.write_bytes(b"MZ")
    cfg = load_config(dest)
    cfg.recovery.launch_path = str(exe)
    actions = build_restart_actions(cfg)
    calls: list[str] = []

    class FakeControl:
        def click_at(self, x, y):
            calls.append("click")

        def double_click_at(self, x, y):
            calls.append("double")

        def wait(self, sec):
            calls.append("wait")

        def launch_as_admin(self, path, arguments=""):
            calls.append("launch")
            return ControlResult(False, None, 0.0, error="denied")

    try:
        run_sequence(actions, cfg, control=FakeControl(), dry_run=False)
        raise AssertionError("expected launch failure to abort sequence")
    except RuntimeError as exc:
        assert "denied" in str(exc)
    assert "click" in calls
    assert calls[-1] == "launch"


def test_resolve_launch_path_prefers_step_then_config(tmp_path: Path) -> None:
    dest = tmp_path / "config.yaml"
    dest.write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    cfg = load_config(dest)
    cfg.recovery.launch_path = r"C:\from-config.exe"
    assert resolve_launch_path(cfg) == r"C:\from-config.exe"
    assert resolve_launch_path(cfg, {"path": r"D:\from-step.exe"}) == r"D:\from-step.exe"


def test_save_process_steps_persists_launch_path(tmp_path: Path) -> None:
    dest = tmp_path / "config.yaml"
    dest.write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    cfg = load_config(dest)
    save_process_steps(dest, cfg.recovery.sequences["restart_app"], launch_path=r"E:\app.exe")
    reloaded = load_config(dest)
    assert reloaded.recovery.launch_path == r"E:\app.exe"


def test_describe_launch_step() -> None:
    text = describe_step(new_launch_step(r"C:\Line\app.exe"))
    assert "admin" in text.lower()
    assert "app.exe" in text.lower()
