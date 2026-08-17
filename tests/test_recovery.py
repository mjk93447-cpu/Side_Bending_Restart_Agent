"""Recovery sequence dry-run order and timing."""

from src.config import load_config
from src.recovery import build_restart_actions, run_sequence


def test_restart_app_action_order() -> None:
    cfg = load_config()
    actions = build_restart_actions(cfg, sequence_name="restart_app")
    kinds = [(a["action"], a.get("point"), a.get("sec")) for a in actions]
    assert kinds[0] == ("click", "stop", None)
    assert kinds[1][0] == "wait" and kinds[1][2] == 0.5
    assert kinds[2] == ("click", "close", None)
    assert kinds[3][0] == "wait" and kinds[3][2] == 1.0
    assert kinds[4] == ("click", "launch_icon", None)
    assert kinds[5][0] == "wait" and kinds[5][2] == 10
    assert kinds[6] == ("click", "start", None)


def test_launch_icon_uses_double_click() -> None:
    cfg = load_config()
    actions = build_restart_actions(cfg)
    icon = next(a for a in actions if a.get("point") == "launch_icon")
    assert icon["click"] == "double"
    stop = next(a for a in actions if a.get("point") == "stop")
    assert stop["click"] == "single"


def test_dry_run_does_not_call_controller() -> None:
    cfg = load_config()
    actions = build_restart_actions(cfg)
    calls: list[tuple] = []

    class BoomControl:
        def click_at(self, x, y):
            calls.append(("click", x, y))

        def double_click_at(self, x, y):
            calls.append(("double", x, y))

        def wait(self, sec):
            calls.append(("wait", sec))

    log = run_sequence(actions, cfg, control=BoomControl(), dry_run=True)
    assert calls == []
    assert [entry["action"] for entry in log] == [
        "click",
        "wait",
        "click",
        "wait",
        "click",
        "wait",
        "click",
    ]
    assert log[0]["point"] == "stop"
    assert log[4]["point"] == "launch_icon"
    assert log[4]["click"] == "double"
    assert log[5]["sec"] == 10
    assert log[-1]["point"] == "start"


def test_live_run_dispatches_clicks_and_waits() -> None:
    cfg = load_config()
    actions = build_restart_actions(cfg)
    calls: list[tuple] = []

    class FakeControl:
        def click_at(self, x, y):
            calls.append(("click", x, y))

        def double_click_at(self, x, y):
            calls.append(("double", x, y))

        def wait(self, sec):
            calls.append(("wait", sec))

    run_sequence(actions, cfg, control=FakeControl(), dry_run=False)
    assert calls[0] == ("click", cfg.points["stop"].x, cfg.points["stop"].y)
    assert calls[1] == ("wait", 0.5)
    assert calls[2] == ("click", cfg.points["close"].x, cfg.points["close"].y)
    assert ("double", cfg.points["launch_icon"].x, cfg.points["launch_icon"].y) in calls
    assert ("wait", 10) in calls
    assert calls[-1] == ("click", cfg.points["start"].x, cfg.points["start"].y)
