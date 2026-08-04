"""Agent V4: preserve V2 production and change only inventory selling.

The policy converts small inventories to cash sooner while still allowing brief
holding when prices are clearly below their reference level. Movement, crop
choice, maintenance, harvesting, seed buying, and liquidation remain V2.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from agents.v2_frozen import PRODUCTS, agent as v2_agent

BASE_PRICE = {
    "WHEAT": 25,
    "CARROT": 35,
    "TOMATO": 60,
    "STRAWBERRY": 120,
    "MELON": 250,
    "EGG": 40,
    "MILK": 70,
    "WOOL": 100,
    "FERTILIZER": 30,
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def sell_orders(observation: Any) -> list[list[Any]]:
    obs = _mapping(observation)
    private = _mapping(obs.get("private"))
    shed = _mapping(private.get("shed"))
    market = _mapping(obs.get("market"))
    prices = _mapping(market.get("prices"))
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    liquidate = day >= 29 or (day == 28 and hour >= 18)

    orders: list[list[Any]] = []
    for product in PRODUCTS:
        quantity = int(shed.get(product, 0) or 0)
        if quantity <= 0:
            continue
        price = float(prices.get(product, BASE_PRICE.get(product, 1)) or 0)
        reference = float(BASE_PRICE.get(product, max(price, 1)))
        attractive = price >= reference
        minimum_lot = 1 if attractive or day >= 24 else 4
        if liquidate or quantity >= minimum_lot:
            orders.append(["SELL", product, quantity])
        if len(orders) >= 10:
            break
    return orders


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    action = v2_agent(observation, configuration)
    existing_non_sell = [
        order for order in action.get("market", [])
        if not (isinstance(order, list) and order[:1] == ["SELL"])
    ]
    action["market"] = (sell_orders(observation) + existing_non_sell)[:10]
    return action
