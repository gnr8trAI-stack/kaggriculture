"""V34.33 isolated strawberry seed-floor experiment.

Single economic mechanism on verified V34.26. Preserve its two-land dairy estate,
16-cow ceiling/window, six-hand dairy service, late staffing, reserve-pasture and
cow-activation rescue, early strawberry specialization, feed, routing, market
behavior and terminal liquidation.

Only when the existing V34.23 strawberry specialization predicate is already
true, maintain a small six-seed STRAWBERRY buffer while fewer than 30 active
strawberry plants exist. Existing strawberry BUY_SEED orders are raised to the
required floor; otherwise one BUY_SEED order is inserted immediately after any
WHEAT survival purchase. No land, labour, livestock, crop-choice or service
priority changes are made.

Economic rationale: the verified V34.26 family peaks near 15 strawberries while
frontier 175k-192k trajectories sustain roughly 30-40 strawberries through the
middle game. V34.32 showed that making the chooser eligible much earlier does
not reliably increase terminal cash, so this test isolates seed availability /
market-order supply as the potential downstream constraint. The maximum staged
capital is only 600 coins, limiting downside if crop slots are already saturated.
"""
from __future__ import annotations
from typing import Any, Dict, List

from agents import v34_26_terminal_liquidation as _base
from agents import v34_21_late_strawberry_specialization as _crop_logic

SEED_FLOOR = 6
MAX_ACTIVE_STRAWBERRIES = 30
_TRIGGER_COUNT = 0


def reset_state() -> None:
    global _TRIGGER_COUNT
    _TRIGGER_COUNT = 0
    _base.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def strawberry_triggered() -> bool:
    return bool(_base.strawberry_triggered())


def terminal_liquidation_triggered() -> bool:
    return bool(_base.terminal_liquidation_triggered())


def seed_floor_trigger_count() -> int:
    return int(_TRIGGER_COUNT)


def _active_strawberries(farm: Dict[str, Any]) -> int:
    count = 0
    for row in farm.get("tiles") or []:
        if not isinstance(row, list):
            continue
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if str(tile.get("kind", "")).upper() != "PLANT":
                continue
            crop = str(tile.get("crop", tile.get("plant", ""))).upper()
            if crop == "STRAWBERRY":
                count += 1
    return count


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    global _TRIGGER_COUNT
    result = dict(_base.agent(observation, configuration))

    # Reuse the exact proven specialization predicate. V34.23 configures the
    # imported crop logic to day>=10, >=8 active cows, >=8000 cash + health.
    if not _crop_logic._eligible(observation):
        return result

    v19 = _crop_logic._v19
    obs = v19._obs(observation)
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    if not isinstance(farms, list) or player >= len(farms):
        return result
    farm = v19._m(farms[player])
    if _active_strawberries(farm) >= MAX_ACTIVE_STRAWBERRIES:
        return result

    private = v19._m(obs.get("private"))
    seeds = v19._m(private.get("seeds"))
    seed_stock = max(0, int(seeds.get("STRAWBERRY", 0) or 0))
    need = max(0, SEED_FLOOR - seed_stock)
    if need <= 0:
        return result

    market: List[List[Any]] = []
    existing_index = None
    existing_qty = 0
    for raw in result.get("market", []):
        if not isinstance(raw, list) or not raw:
            continue
        order = list(raw)
        if (str(order[0]).upper() == "BUY_SEED" and len(order) >= 3
                and str(order[1]).upper() == "STRAWBERRY"):
            existing_index = len(market)
            try:
                existing_qty = max(0, int(order[2]))
            except Exception:
                existing_qty = 0
            order = ["BUY_SEED", "STRAWBERRY", max(existing_qty, need)]
        market.append(order)

    changed = existing_index is not None and max(existing_qty, need) > existing_qty
    if existing_index is None:
        insert_at = 0
        # Keep survival wheat ahead of speculative seed inventory.
        while insert_at < len(market):
            order = market[insert_at]
            if (str(order[0]).upper() == "BUY_PRODUCT" and len(order) >= 2
                    and str(order[1]).upper() == "WHEAT"):
                insert_at += 1
            else:
                break
        market.insert(insert_at, ["BUY_SEED", "STRAWBERRY", need])
        changed = True

    if changed:
        _TRIGGER_COUNT += 1
    result["market"] = market[:10]
    return result
