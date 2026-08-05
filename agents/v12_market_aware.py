"""V12 market-aware policy overlay for the V11 execution planner.

V11's operational scheduler is retained, but its crop selector is replaced with
an inventory-curve-aware portfolio policy. The override is intentionally small
so benchmark differences are attributable to crop economics rather than routing.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from agents import v11_adaptive_planner as planner


MARKET_PARAMS = {
    "WHEAT": (400.0, "log", 0.20),
    "CARROT": (450.0, "sqrt", 0.70),
    "TOMATO": (200.0, "sqrt", 0.60),
    "STRAWBERRY": (100.0, "linear", 1.60),
    "MELON": (300.0, "sq", 3.60),
}

# Portfolio caps prevent a short-cycle staple from consuming the whole field.
MAX_SHARE = {
    "WHEAT": 0.20,
    "CARROT": 0.20,
    "TOMATO": 0.35,
    "STRAWBERRY": 0.20,
    "MELON": 0.65,
}

STRATEGIC_WEIGHT = {
    "WHEAT": 0.72,
    "CARROT": 0.82,
    "TOMATO": 1.05,
    "STRAWBERRY": 0.92,
    "MELON": 1.22,
}


def _shape(name: str, value: float) -> float:
    value = max(0.0, value)
    if name == "linear":
        return value
    if name == "sq":
        return value * value
    if name == "sqrt":
        return math.sqrt(value)
    if name == "log10":
        return math.log10(1.0 + value)
    return math.log1p(value)


def projected_price(crop: str, inventory: float) -> float:
    """Return documented post-glut sell price for the five crops."""
    spec = planner.CROPS[crop]
    base = float(spec["base"])
    throughput, function, target = MARKET_PARAMS[crop]
    distance = max(0.0, inventory - 10000.0)
    if distance <= 0:
        return base
    denominator = _shape(function, throughput)
    amplitude = target * base / denominator if denominator > 0 else 0.0
    raw = base - amplitude * _shape(function, distance)
    return float(max(1, int(raw + 0.5)))


def _demand_bonus(crop: str, shops: Sequence[str]) -> float:
    joined = " ".join(str(item).upper() for item in shops)
    if crop == "WHEAT":
        return 8.0 * sum(name in joined for name in ("BAKERY", "PIZZA", "BRUNCH", "ICE_CREAM"))
    if crop == "CARROT":
        return 18.0 if "PET" in joined else 0.0
    if crop == "TOMATO":
        return 14.0 if ("PIZZA" in joined or "FARMERS" in joined) else 0.0
    if crop == "STRAWBERRY":
        return 16.0 * sum(name in joined for name in ("BRUNCH", "ICE_CREAM", "SMOOTHIE", "FARMERS"))
    return 0.0


def market_aware_scores(
    obs: Mapping[str, Any], farm: Mapping[str, Any]
) -> Tuple[Dict[str, float], Dict[str, float]]:
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", [])
    opponent = planner._mapping(farms[1 - player]) if isinstance(farms, list) and len(farms) > 1 else {}
    own = planner._crop_counts(farm.get("tiles", []))
    other = planner._crop_counts(opponent.get("tiles", []))
    market = planner._mapping(obs.get("market"))
    prices = planner._mapping(market.get("prices"))
    inventories = planner._mapping(market.get("inventory"))
    shops = list(planner._mapping(obs.get("town")).get("unlocked_shops", []))
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    remaining = planner._remaining_days(day, hour)

    scores: Dict[str, float] = {}
    projected: Dict[str, float] = {}
    for crop, spec in planner.CROPS.items():
        if remaining < float(spec["peak"] + planner.ENDGAME_BUFFER_DAYS):
            scores[crop] = float("-inf")
            projected[crop] = float(prices.get(crop, spec["base"]) or spec["base"])
            continue

        visible_units = (own[crop] + other[crop]) * float(spec["yield"])
        current_inventory = float(inventories.get(crop, 10000) or 10000)
        projected_inventory = current_inventory + visible_units
        curve_price = projected_price(crop, projected_inventory)
        live_price = float(prices.get(crop, spec["base"]) or spec["base"])
        # Early sellers capture part of the live quote, while later units face
        # the visible production glut. This blend is deliberately conservative.
        expected_price = 0.45 * live_price + 0.55 * curve_price
        projected[crop] = expected_price

        margin = expected_price * float(spec["yield"]) - float(spec["seed"])
        velocity = margin / max(1.0, float(spec["peak"]))
        crowd_ratio = visible_units / max(1.0, MARKET_PARAMS[crop][0])
        nonlinear_risk = 1.0 + crowd_ratio * crowd_ratio
        score = velocity * STRATEGIC_WEIGHT[crop] / nonlinear_risk
        score += _demand_bonus(crop, shops)

        # Preserve V10's proven opening economics unless the shared visible
        # melon exposure or current quote signals a genuine collapse.
        if crop == "MELON" and live_price >= 150 and other[crop] < 8 and remaining >= 12:
            score = max(score, 105.0 - 3.0 * own[crop])
        scores[crop] = score
    return scores, projected


def choose_crop(
    obs: Mapping[str, Any], farm: Mapping[str, Any]
) -> Tuple[Optional[str], Dict[str, float]]:
    scores, _ = market_aware_scores(obs, farm)
    own = planner._crop_counts(farm.get("tiles", []))
    total = sum(own.values())
    ranked = sorted(
        ((score, crop) for crop, score in scores.items() if score != float("-inf")),
        reverse=True,
    )
    if not ranked:
        return None, scores

    best_score = ranked[0][0]
    for score, crop in ranked:
        share = own[crop] / max(1, total)
        if share < MAX_SHARE[crop] or total < 5:
            # Do not diversify into an economically broken crop merely to meet
            # a quota; alternatives must retain at least 55% of the best score.
            if score >= best_score * 0.55:
                return crop, scores
    return ranked[0][1], scores


# V11's agent resolves choose_crop through its module globals on every turn.
planner.choose_crop = choose_crop


def agent(observation: Any, configuration: Any = None):
    return planner.agent(observation, configuration)
