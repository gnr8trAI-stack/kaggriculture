"""Agent V6: preserve frozen V2 and adjust only wheat seed inventory.

The intervention is deliberately narrow and guaranteed to occur during ordinary
play: keep a slightly larger wheat-seed buffer early in the season so idle empty
tiles are less likely to wait for the next market cycle.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from agents.v2_frozen import agent as v2_agent


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def desired_seed_buffer(day: int, hands: int) -> int:
    base = max(2, 1 + hands)
    if day < 20:
        return base + 2
    if day < 26:
        return base + 1
    return base


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    action = v2_agent(observation, configuration)
    obs = _mapping(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", [])
    if not isinstance(farms, list) or player >= len(farms):
        return action

    farm = _mapping(farms[player])
    hands = farm.get("hands", [])
    hand_count = len(hands) if isinstance(hands, list) else 0
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    liquidate = day >= 29 or (day == 28 and hour >= 18)
    if liquidate:
        return action

    private = _mapping(obs.get("private"))
    seeds = _mapping(private.get("seeds"))
    wheat_seeds = int(seeds.get("WHEAT", 0) or 0)
    target = desired_seed_buffer(day, hand_count)
    deficit = max(0, target - wheat_seeds)
    money = float(farm.get("money", 0) or 0)
    affordable = min(deficit, int(money // 10))

    market = [
        order for order in action.get("market", [])
        if not (isinstance(order, list) and order[:2] == ["BUY_SEED", "WHEAT"])
    ]
    if affordable > 0 and len(market) < 10:
        market.append(["BUY_SEED", "WHEAT", affordable])
    action["market"] = market[:10]
    return action
