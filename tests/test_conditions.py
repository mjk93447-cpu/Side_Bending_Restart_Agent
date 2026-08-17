"""AND/OR condition evaluation for ocr_count rules."""

from src.conditions import ConditionContext, evaluate_rule, evaluate_rules
from src.config import load_config
from src.ocr_engine import TextRegion


def _nan_regions(n: int) -> list[TextRegion]:
    return [
        TextRegion(text="NaN", bbox=(0, 0, 10, 10), confidence=1.0, center=(5, 5), source="mock")
        for _ in range(n)
    ]


def _ctx(count: int) -> ConditionContext:
    cfg = load_config()
    return ConditionContext(
        nan_counts={"table": count},
        regions={"table": _nan_regions(count)},
        config=cfg,
    )


def test_ocr_count_and_rule_fires_at_threshold() -> None:
    cfg = load_config()
    rule = next(r for r in cfg.rules if r["name"] == "nan_table_freeze")
    assert evaluate_rule(rule, _ctx(21)) is True
    assert evaluate_rule(rule, _ctx(20)) is False


def test_all_requires_every_child() -> None:
    rule = {
        "name": "and_demo",
        "enabled": True,
        "when": {
            "all": [
                {"type": "ocr_count", "roi": "table", "pattern": r"(?i)\bnan\b", "min": 21},
                {"type": "ocr_count", "roi": "table", "pattern": r"(?i)\bnan\b", "min": 10},
            ]
        },
        "then": "restart_app",
    }
    assert evaluate_rule(rule, _ctx(21)) is True
    assert evaluate_rule(rule, _ctx(15)) is False


def test_any_or_logic() -> None:
    rule = {
        "name": "or_demo",
        "enabled": True,
        "when": {
            "any": [
                {"type": "ocr_count", "roi": "table", "pattern": r"(?i)\berror\b", "min": 1},
                {"type": "ocr_count", "roi": "table", "pattern": r"(?i)\bnan\b", "min": 21},
            ]
        },
        "then": "restart_app",
    }
    assert evaluate_rule(rule, _ctx(21)) is True
    assert evaluate_rule(rule, _ctx(0)) is False


def test_disabled_rule_never_fires() -> None:
    rule = {
        "name": "off",
        "enabled": False,
        "when": {"all": [{"type": "ocr_count", "roi": "table", "min": 1}]},
        "then": "restart_app",
    }
    assert evaluate_rule(rule, _ctx(99)) is False


def test_unimplemented_condition_types_do_not_match() -> None:
    rule = {
        "name": "future",
        "enabled": True,
        "when": {"all": [{"type": "error_text", "roi": "table", "pattern": "ERROR"}]},
        "then": "restart_app",
    }
    assert evaluate_rule(rule, _ctx(21)) is False
    rule2 = {
        "name": "mse",
        "enabled": True,
        "when": {"all": [{"type": "screen_frozen_mse"}]},
        "then": "restart_app",
    }
    assert evaluate_rule(rule2, _ctx(21)) is False


def test_evaluate_rules_returns_first_matching_then() -> None:
    cfg = load_config()
    matched = evaluate_rules(cfg.rules, _ctx(21))
    assert matched == "restart_app"
    assert evaluate_rules(cfg.rules, _ctx(0)) is None
