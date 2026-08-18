"""Process sequence editing: waits, enable/disable, add/remove."""

from pathlib import Path

from src.config import load_config, save_config
from src.process_editor import (
    delete_step,
    describe_step,
    enabled_steps,
    flatten_wait_step,
    insert_step,
    move_step,
    new_click_step,
    new_wait_step,
    set_step_enabled,
    set_wait_seconds,
)


def test_flatten_wait_resolves_named_sources() -> None:
    step = flatten_wait_step(
        {"action": "wait", "from": "startup_wait_sec"},
        startup_wait_sec=12,
        stop_confirm_wait_sec=1,
    )
    assert step["action"] == "wait"
    assert step["sec"] == 12
    assert "from" not in step


def test_enabled_steps_skips_disabled() -> None:
    steps = [
        {"action": "click", "point": "stop", "enabled": True},
        {"action": "wait", "sec": 1, "enabled": False},
        {"action": "click", "point": "close", "enabled": True},
    ]
    assert [s.get("point") or s.get("sec") for s in enabled_steps(steps)] == ["stop", "close"]


def test_insert_delete_and_move_steps() -> None:
    steps = [new_click_step("stop"), new_wait_step(1), new_click_step("close")]
    steps = insert_step(steps, 2, new_wait_step(5))
    assert steps[2]["sec"] == 5
    steps = move_step(steps, 2, -1)
    assert steps[1]["sec"] == 5
    steps = delete_step(steps, 1)
    assert [s.get("point") or s.get("sec") for s in steps] == ["stop", 1, "close"]


def test_set_wait_and_disable() -> None:
    steps = [new_wait_step(10)]
    steps = set_wait_seconds(steps, 0, 25)
    assert steps[0]["sec"] == 25
    steps = set_step_enabled(steps, 0, False)
    assert steps[0]["enabled"] is False
    assert enabled_steps(steps) == []


def test_describe_click_and_wait() -> None:
    assert "stop" in describe_step(new_click_step("stop")).lower()
    assert "5" in describe_step(new_wait_step(5))


def test_save_process_steps_does_not_clobber_calibration(tmp_path: Path) -> None:
    dest = tmp_path / "config.yaml"
    dest.write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    stale = load_config(dest)
    calibrated = load_config(dest)
    calibrated.points["stop"].x = 1234
    calibrated.rois["table"].x = 42
    save_config(dest, calibrated)
    from src.process_editor import save_process_steps

    save_process_steps(dest, stale.recovery.sequences["restart_app"])
    reloaded = load_config(dest)
    assert reloaded.points["stop"].x == 1234
    assert reloaded.rois["table"].x == 42
