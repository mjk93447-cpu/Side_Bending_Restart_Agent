"""Recovery sequence dry-run order and timing."""

from src.config import load_config
from src.recovery import build_restart_actions, run_sequence


def test_restart_app_action_order() -> None:
    cfg = load_config()
    actions = build_restart_actions(cfg, sequence_name="restart_app")
    kinds = [(a["action"], a.get("point"), a.get("sec")) for a in actions]
    assert kinds[0] == ("click", "stop", None)
    assert kinds[1][0] == "wait" and kinds[1][2] == 1
    assert kinds[2] == ("click", "confirm_yes", None)
    assert kinds[3][0] == "wait" and kinds[3][2] == 0.5
    assert kinds[4] == ("click", "close", None)
    assert kinds[5][0] == "wait" and kinds[5][2] == 1.0
    assert kinds[6] == ("click", "launch_icon", None)
    assert kinds[7][0] == "wait" and kinds[7][2] == 10
    assert kinds[8] == ("click", "start", None)


def test_startup_wait_follows_config() -> None:
    cfg = load_config()
    cfg.recovery.startup_wait_sec = 25
    actions = build_restart_actions(cfg)
    wait_after_icon = None
    for index, action in enumerate(actions):
        if action.get("point") == "launch_icon":
            wait_after_icon = actions[index + 1]
            break
    assert wait_after_icon is not None
    assert wait_after_icon["action"] == "wait"
    assert wait_after_icon["sec"] == 25


def test_launch_icon_uses_double_click() -> None:
    cfg = load_config()
    actions = build_restart_actions(cfg)
    icon = next(a for a in actions if a.get("point") == "launch_icon")
    assert icon["click"] == "double"
    yes = next(a for a in actions if a.get("point") == "confirm_yes")
    assert yes["click"] == "single"


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
        "wait",
        "click",
    ]
    assert log[0]["point"] == "stop"
    assert log[2]["point"] == "confirm_yes"
    assert log[6]["point"] == "launch_icon"
    assert log[6]["click"] == "double"
    assert log[7]["sec"] == 10
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
    assert calls[1] == ("wait", 1)
    assert calls[2] == ("click", cfg.points["confirm_yes"].x, cfg.points["confirm_yes"].y)
    assert calls[3] == ("wait", 0.5)
    assert calls[4] == ("click", cfg.points["close"].x, cfg.points["close"].y)
    assert ("double", cfg.points["launch_icon"].x, cfg.points["launch_icon"].y) in calls
    assert ("wait", 10) in calls
    assert calls[-1] == ("click", cfg.points["start"].x, cfg.points["start"].y)
