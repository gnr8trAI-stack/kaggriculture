"""Agent V3b: conservative crop economics layered over frozen Agent V2.

V3b keeps wheat as the default production engine. It only diverts planting to a
premium crop when all of the following are true:

- the seed is already available;
- the crop can mature with a safety margin;
- its expected return materially exceeds wheat;
- premium exposure stays within a small cap;
- the farm retains a cash reserve and a wheat seed buffer.

This policy deliberately avoids speculative bulk purchases and never suppresses
V2's proven wheat replenishment order.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from agents.v2_frozen import agent as v2_agent

PREMIUM_CROPS = ("CARROT", "TOMATO", "STRAWBERRY", "MELON")
SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
BASE_PRICE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250}
FIRST_YIELD_DAY = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
EXPECTED_UNITS = {"WHEAT": 4.0, "CARROT": 3.0, "TOMATO": 4.0, "STRAWBERRY": 3.0, "MELON": 4.0}
MIN_ADVANTAGE = 1.45
CASH_RESERVE = 500.0
MAX_PREMIUM_SEEDS = 2


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _farm_money(obs: Mapping[str, Any]) -> float:
    farms = obs.get("farms", [])
    player = int(obs.get("player", 0) or 0)
    try:
        return float(farms[player].get("money", 0) or 0)
    except Exception:
        return 0.0


def _price(obs: Mapping[str, Any], crop: str) -> float:
    prices = _mapping(_mapping(obs.get("market")).get("prices"))
    return float(prices.get(crop, BASE_PRICE[crop]) or BASE_PRICE[crop])


def expected_profit(obs: Mapping[str, Any], crop: str) -> float:
    day = int(obs.get("day", 0) or 0)
    remaining_days = max(0, 30 - day)
    maturity = FIRST_YIELD_DAY[crop]
    safety_margin = 3 if crop in {"TOMATO", "STRAWBERRY", "MELON"} else 2
    if remaining_days <= maturity + safety_margin:
        return float("-inf")

    price = _price(obs, crop)
    price_ratio = max(0.05, price / BASE_PRICE[crop])
    glut_penalty = 1.0
    if crop in {"STRAWBERRY", "MELON"} and price_ratio < 0.9:
        glut_penalty = 0.45
    elif crop in {"CARROT", "TOMATO"} and price_ratio < 0.75:
        glut_penalty = 0.65

    maturity_discount = min(1.0, remaining_days / (maturity + 8))
    revenue = EXPECTED_UNITS[crop] * price * glut_penalty * maturity_discount
    return revenue - SEED_COST[crop]


def choose_premium_crop(observation: Any) -> Optional[str]:
    obs = _mapping(observation)
    private = _mapping(obs.get("private"))
    seeds = _mapping(private.get("seeds"))
    money = _farm_money(obs)
    if money < CASH_RESERVE:
        return None

    wheat_profit = expected_profit(obs, "WHEAT")
    candidates = []
    for crop in PREMIUM_CROPS:
        available = int(seeds.get(crop, 0) or 0)
        if available <= 0:
            continue
        profit = expected_profit(obs, crop)
        if profit == float("-inf"):
            continue
        advantage = profit / max(1.0, wheat_profit)
        if advantage >= MIN_ADVANTAGE:
            candidates.append((advantage, profit, -SEED_COST[crop], crop))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][3]


def _replace_available_plant_actions(action: Dict[str, Any], crop: str, quantity: int) -> int:
    remaining = max(0, quantity)
    if remaining == 0:
        return 0

    farmer = action.get("farmer")
    if isinstance(farmer, list) and farmer[:1] == ["PLANT"]:
        action["farmer"] = ["PLANT", crop]
        remaining -= 1

    hands = action.get("hands", [])
    for index, hand_action in enumerate(hands):
        if remaining == 0:
            break
        if isinstance(hand_action, list) and hand_action[:1] == ["PLANT"]:
            hands[index] = ["PLANT", crop]
            remaining -= 1
    return quantity - remaining


def _maybe_buy_one_premium_seed(action: Dict[str, Any], observation: Any) -> None:
    obs = _mapping(observation)
    day = int(obs.get("day", 0) or 0)
    if day > 14:
        return

    private = _mapping(obs.get("private"))
    seeds = _mapping(private.get("seeds"))
    premium_total = sum(int(seeds.get(crop, 0) or 0) for crop in PREMIUM_CROPS)
    if premium_total >= MAX_PREMIUM_SEEDS:
        return

    money = _farm_money(obs)
    wheat_seeds = int(seeds.get("WHEAT", 0) or 0)
    if money < CASH_RESERVE + 100 or wheat_seeds < 2:
        return

    wheat_profit = expected_profit(obs, "WHEAT")
    candidates = []
    for crop in PREMIUM_CROPS:
        profit = expected_profit(obs, crop)
        if profit == float("-inf"):
            continue
        advantage = profit / max(1.0, wheat_profit)
        if advantage >= MIN_ADVANTAGE + 0.25:
            candidates.append((advantage, profit, -SEED_COST[crop], crop))
    if not candidates:
        return

    candidates.sort(reverse=True)
    crop = candidates[0][3]
    market = action.setdefault("market", [])
    if len(market) < 10:
        market.append(["BUY_SEED", crop, 1])


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    action = v2_agent(observation, configuration)
    obs = _mapping(observation)
    private = _mapping(obs.get("private"))
    seeds = _mapping(private.get("seeds"))

    crop = choose_premium_crop(observation)
    if crop is not None:
        available = min(MAX_PREMIUM_SEEDS, int(seeds.get(crop, 0) or 0))
        _replace_available_plant_actions(action, crop, available)

    _maybe_buy_one_premium_seed(action, observation)
    action["market"] = list(action.get("market", []))[:10]
    return action
