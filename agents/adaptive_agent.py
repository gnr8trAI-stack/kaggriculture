"""Dependency-free Kaggriculture baseline agent.

The policy deliberately favours correctness and fast execution over speculative
complexity. It services visible farm assets, buys a small wheat seed buffer,
and liquidates shed inventory near the end of the season.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")


def _as_dict(observation: Any) -> Dict[str, Any]:
    if isinstance(observation, dict):
        return observation
    result: Dict[str, Any] = {}
    for name in ("player", "day", "hour", "farms", "private", "market", "town"):
        try:
            result[name] = getattr(observation, name)
        except Exception:
            pass
    return result


def _tile_task(tile: Any) -> List[Any] | None:
    if not isinstance(tile, Mapping):
        return None
    kind = tile.get("kind")
    if kind == "PLANT":
        if int(tile.get("yield_units", 0)) > 0:
            return ["HARVEST"]
        if not tile.get("watered_today", False):
            return ["WATER"]
    if kind in ("COOP", "PASTURE") and tile.get("animal"):
        if int(tile.get("yield_units", 0)) > 0:
            return ["HARVEST"]
        if not tile.get("fed_today", False):
            return ["FEED"]
        if not tile.get("cared_today", False):
            return ["CARE"]
        if tile.get("fertilizer_available", False):
            return ["COLLECT_FERTILIZER"]
    if kind == "WEED":
        return ["DIG"]
    return None


def _sell_orders(obs: Mapping[str, Any], liquidate: bool) -> List[List[Any]]:
    shed = obs.get("private", {}).get("shed", {})
    orders: List[List[Any]] = []
    for product in PRODUCTS:
        quantity = int(shed.get(product, 0))
        if quantity > 0 and (liquidate or quantity >= 10):
            orders.append(["SELL", product, quantity])
        if len(orders) == 10:
            break
    return orders


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    obs = _as_dict(observation)
    player = int(obs.get("player", 0))
    farms = obs.get("farms", [])
    if player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    farm = farms[player]
    hands = list(farm.get("hands", []))
    action = {"farmer": ["PASS"], "hands": [["PASS"] for _ in hands], "market": []}
    tiles = farm.get("tiles", [])
    position = farm.get("farmer", [0, 0])

    try:
        x, y = int(position[0]), int(position[1])
        task = _tile_task(tiles[y][x])
        if task:
            action["farmer"] = task
        elif tiles[y][x] is None and int(obs.get("private", {}).get("seeds", {}).get("WHEAT", 0)) > 0:
            action["farmer"] = ["PLANT", "WHEAT"]
    except Exception:
        pass

    day, hour = int(obs.get("day", 0)), int(obs.get("hour", 0))
    liquidate = day >= 29 or (day == 28 and hour >= 18)
    market = _sell_orders(obs, liquidate)

    seeds = int(obs.get("private", {}).get("seeds", {}).get("WHEAT", 0))
    money = float(farm.get("money", 0))
    if not liquidate and seeds < 2 and money >= 20 and len(market) < 10:
        market.append(["BUY_SEED", "WHEAT", 2 - seeds])

    action["market"] = market[:10]
    return action
