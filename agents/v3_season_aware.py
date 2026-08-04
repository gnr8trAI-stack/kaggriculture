"""Agent V3: season-aware crop selection layered over the proven V2 planner.

This experiment intentionally changes only crop and seed economics. Movement,
maintenance, harvesting, reservations, and liquidation remain inherited from
frozen Agent V2 so benchmark deltas are easier to attribute.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from agents.v2_frozen import agent as v2_agent

CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
BASE_PRICE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250}
FIRST_YIELD_DAY = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
EXPECTED_UNITS = {"WHEAT": 4.0, "CARROT": 3.0, "TOMATO": 4.0, "STRAWBERRY": 3.0, "MELON": 4.0}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def crop_score(crop: str, day: int, price: float) -> float:
    """Return a conservative expected profit-per-seed-dollar score."""
    remaining_days = max(0, 30 - day)
    maturity = FIRST_YIELD_DAY[crop]
    if remaining_days <= maturity + 1:
        return float("-inf")

    price_ratio = max(0.05, price / BASE_PRICE[crop])
    glut_penalty = 1.0
    if crop in {"STRAWBERRY", "MELON"} and price_ratio < 0.8:
        glut_penalty = 0.55
    elif crop in {"TOMATO", "CARROT"} and price_ratio < 0.65:
        glut_penalty = 0.75

    maturity_discount = max(0.25, min(1.0, remaining_days / (maturity + 5)))
    expected_revenue = EXPECTED_UNITS[crop] * price * glut_penalty * maturity_discount
    return (expected_revenue - SEED_COST[crop]) / SEED_COST[crop]


def choose_crop(observation: Any) -> Optional[str]:
    obs = _as_mapping(observation)
    day = int(obs.get("day", 0) or 0)
    prices = _as_mapping(_as_mapping(obs.get("market")).get("prices"))
    farms = obs.get("farms", [])
    player = int(obs.get("player", 0) or 0)
    money = 0.0
    try:
        money = float(farms[player].get("money", 0) or 0)
    except Exception:
        pass

    reserve_cash = 250.0
    candidates = []
    for crop in CROPS:
        if money - SEED_COST[crop] < reserve_cash:
            continue
        price = float(prices.get(crop, BASE_PRICE[crop]) or BASE_PRICE[crop])
        candidates.append((crop_score(crop, day, price), -SEED_COST[crop], crop))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][2] if candidates[0][0] > 0 else None


def _replace_plant_actions(action: Dict[str, Any], crop: str) -> None:
    farmer = action.get("farmer")
    if isinstance(farmer, list) and farmer[:1] == ["PLANT"]:
        action["farmer"] = ["PLANT", crop]
    hands = action.get("hands", [])
    for index, hand_action in enumerate(hands):
        if isinstance(hand_action, list) and hand_action[:1] == ["PLANT"]:
            hands[index] = ["PLANT", crop]


def _replace_seed_order(action: Dict[str, Any], observation: Any, crop: str) -> None:
    obs = _as_mapping(observation)
    private = _as_mapping(obs.get("private"))
    seeds = _as_mapping(private.get("seeds"))
    target_have = int(seeds.get(crop, 0) or 0)

    market = action.get("market", [])
    replaced = False
    for index, order in enumerate(market):
        if isinstance(order, list) and order[:2] == ["BUY_SEED", "WHEAT"]:
            quantity = int(order[2]) if len(order) > 2 else 1
            market[index] = ["BUY_SEED", crop, max(1, quantity - target_have)]
            replaced = True
            break
    if not replaced and target_have == 0 and len(market) < 10:
        market.append(["BUY_SEED", crop, 1])


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    action = v2_agent(observation, configuration)
    crop = choose_crop(observation)
    if crop is None:
        return action
    _replace_plant_actions(action, crop)
    _replace_seed_order(action, observation, crop)
    return action
