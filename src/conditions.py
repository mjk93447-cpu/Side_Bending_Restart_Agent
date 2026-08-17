"""AND/OR rule evaluation. Prototype implements ocr_count only."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from src.config import AppConfig
from src.nan_counter import count_nan_tokens
from src.ocr_engine import TextRegion

logger = logging.getLogger(__name__)

UNIMPLEMENTED_TYPES = frozenset({"error_text", "screen_frozen_mse"})


@dataclass
class ConditionContext:
    nan_counts: dict[str, int] = field(default_factory=dict)
    regions: dict[str, list[TextRegion]] = field(default_factory=dict)
    config: Optional[AppConfig] = None


def evaluate_rules(rules: list[dict[str, Any]], ctx: ConditionContext) -> Optional[str]:
    for rule in rules:
        if evaluate_rule(rule, ctx):
            return str(rule.get("then") or "")
    return None


def evaluate_rule(rule: dict[str, Any], ctx: ConditionContext) -> bool:
    if not rule.get("enabled", True):
        return False
    when = rule.get("when") or {}
    return _eval_node(when, ctx)


def _eval_node(node: dict[str, Any], ctx: ConditionContext) -> bool:
    if "all" in node:
        children = node["all"] or []
        return bool(children) and all(_eval_node(child, ctx) for child in children)
    if "any" in node:
        children = node["any"] or []
        return any(_eval_node(child, ctx) for child in children)
    return _eval_leaf(node, ctx)


def _eval_leaf(cond: dict[str, Any], ctx: ConditionContext) -> bool:
    cond_type = str(cond.get("type") or "")
    if cond_type in UNIMPLEMENTED_TYPES:
        logger.info("Condition type %s is not implemented yet", cond_type)
        return False
    if cond_type == "ocr_count":
        return _eval_ocr_count(cond, ctx)
    logger.warning("Unknown condition type: %s", cond_type)
    return False


def _eval_ocr_count(cond: dict[str, Any], ctx: ConditionContext) -> bool:
    roi = str(cond.get("roi") or "table")
    minimum = int(cond.get("min") or 0)
    pattern = cond.get("pattern")
    n0n = bool(ctx.config.ocr.n0n_correction) if ctx.config is not None else False
    regions = ctx.regions.get(roi)
    if regions is not None:
        count = count_nan_tokens(regions, pattern=pattern, n0n_correction=n0n)
    else:
        count = int(ctx.nan_counts.get(roi, 0))
    return count >= minimum
