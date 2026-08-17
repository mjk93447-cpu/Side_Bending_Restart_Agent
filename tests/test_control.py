"""Control engine uses pyautogui with FAILSAFE."""

from src.config import ControlConfig
from src.control import ControlEngine


def test_click_at_moves_then_clicks(monkeypatch) -> None:
    calls: list[tuple] = []

    class FakePyauto:
        FAILSAFE = False

        @staticmethod
        def moveTo(x, y, duration=0):
            calls.append(("move", x, y, duration))

        @staticmethod
        def click():
            calls.append(("click",))

        @staticmethod
        def doubleClick():
            calls.append(("double",))

    monkeypatch.setattr("src.control.pyautogui", FakePyauto)
    engine = ControlEngine(ControlConfig(move_duration=0.3, click_pause=0.0, failsafe=True))
    result = engine.click_at(10, 20)
    assert result.success is True
    assert result.coords == (10, 20)
    assert calls[0] == ("move", 10, 20, 0.3)
    assert calls[1] == ("click",)
    assert FakePyauto.FAILSAFE is True


def test_double_click_at(monkeypatch) -> None:
    calls: list[str] = []

    class FakePyauto:
        FAILSAFE = False

        @staticmethod
        def moveTo(x, y, duration=0):
            calls.append("move")

        @staticmethod
        def doubleClick():
            calls.append("double")

    monkeypatch.setattr("src.control.pyautogui", FakePyauto)
    engine = ControlEngine(ControlConfig(click_pause=0.0, failsafe=False))
    engine.double_click_at(1, 2)
    assert calls == ["move", "double"]
    assert FakePyauto.FAILSAFE is False


def test_wait_sleeps(monkeypatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr("src.control.time.sleep", slept.append)
    engine = ControlEngine(ControlConfig(click_pause=0.0))
    engine.wait(1.5)
    assert slept == [1.5]
