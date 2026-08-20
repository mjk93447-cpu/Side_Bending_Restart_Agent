"""Recovery sequence dry-run order and timing."""

from src.config import load_config
from src.control import ControlResult
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
    assert kinds[5][0] == "wait" and kinds[5][2] == 1
    assert kinds[6] == ("click", "confirm_yes", None)
    assert kinds[7][0] == "wait" and kinds[7][2] == 5
    assert kinds[8][0] == "launch"
    assert kinds[9][0] == "wait" and kinds[9][2] == 10
    assert kinds[10] == ("click", "start", None)
    yes_clicks = [a for a in actions if a.get("point") == "confirm_yes"]
    assert len(yes_clicks) == 2
    assert not any(a.get("point") == "launch_icon" for a in actions)


def test_wait_after_launch_uses_step_seconds() -> None:
    cfg = load_config()
    steps = cfg.recovery.sequences["restart_app"]
    for index, step in enumerate(steps):
        if step.get("action") == "launch" and index + 1 < len(steps):
            steps[index + 1]["sec"] = 25
            break
    actions = build_restart_actions(cfg)
    wait_after = None
    for index, action in enumerate(actions):
        if action.get("action") == "launch":
            wait_after = actions[index + 1]
            break
    assert wait_after is not None
    assert wait_after["action"] == "wait"
    assert wait_after["sec"] == 25


def test_launch_step_is_admin_process() -> None:
    cfg = load_config()
    actions = build_restart_actions(cfg)
    launch = next(a for a in actions if a["action"] == "launch")
    assert launch["as_admin"] is True
    yes_clicks = [a for a in actions if a.get("point") == "confirm_yes"]
    assert len(yes_clicks) == 2
    assert all(a["click"] == "single" for a in yes_clicks)


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

        def launch_as_admin(self, path, arguments=""):
            calls.append(("launch_admin", path, arguments))

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
        "launch",
        "wait",
        "click",
    ]
    assert log[0]["point"] == "stop"
    assert log[2]["point"] == "confirm_yes"
    assert log[4]["point"] == "close"
    assert log[6]["point"] == "confirm_yes"
    assert log[7]["sec"] == 5
    assert log[8]["action"] == "launch"
    assert log[9]["sec"] == 10
    assert log[-1]["point"] == "start"


def test_live_run_dispatches_clicks_waits_and_admin_launch() -> None:
    cfg = load_config()
    cfg.recovery.launch_path = r"C:\line\app.exe"
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
    assert calls[0] == ("click", cfg.points["stop"].x, cfg.points["stop"].y)
    assert calls[1] == ("wait", 1)
    assert calls[2] == ("click", cfg.points["confirm_yes"].x, cfg.points["confirm_yes"].y)
    assert calls[3] == ("wait", 0.5)
    assert calls[4] == ("click", cfg.points["close"].x, cfg.points["close"].y)
    assert calls[5] == ("wait", 1)
    assert calls[6] == ("click", cfg.points["confirm_yes"].x, cfg.points["confirm_yes"].y)
    assert calls[7] == ("wait", 5)
    assert ("launch_admin", r"C:\line\app.exe", "") in calls
    assert not any(c[0] == "double" for c in calls)
    assert ("wait", 10) in calls
    assert calls[-1] == ("click", cfg.points["start"].x, cfg.points["start"].y)


def test_disabled_steps_are_skipped() -> None:
    cfg = load_config()
    steps = cfg.recovery.sequences["restart_app"]
    for step in steps:
        if step.get("point") == "start":
            step["enabled"] = False
    actions = build_restart_actions(cfg)
    assert actions[-1].get("point") != "start"
    assert any(a.get("action") == "launch" for a in actions)
