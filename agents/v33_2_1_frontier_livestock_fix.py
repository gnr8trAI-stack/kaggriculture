"""V33.2.1 Frontier Livestock Fix.

Corrects three structural defects in V33.2:
1) V33.2's replay-driven _market allocator was monkey-patched onto v33_industrial
   but never called by v33_industrial.agent; this wrapper invokes it explicitly.
2) V19's inherited four-cow ceiling is bypassed with a replay-derived 14/22
   livestock target.
3) livestock service/build capacity scales beyond the inherited two-hand crew.

The crop/land routing core remains V33/V19.2; this wrapper changes only the
frontier market allocator and livestock execution capacity.
"""
from __future__ import annotations
from typing import Any, Dict, Mapping
from agents import v33_2_industrial_frontier as _v332

_v33 = _v332._v33
_v192 = _v33._v192
_v19 = _v192._v19


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _frontier_target(day: int, lands: int) -> int:
    if lands < 2 or day > 25:
        return 0
    if lands == 2:
        return 8 if day <= 18 else 6
    if lands == 3:
        return 14 if day <= 22 else 12
    return 22 if day <= 18 else 18


def reset_state() -> None:
    _v33.reset_state()


def reset_telemetry() -> None:
    _v33.reset_telemetry()


def get_telemetry(clear: bool = False):
    return _v33.get_telemetry(clear=clear)


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    obs = _v19._obs(observation)
    player = int(obs.get('player', 0) or 0)
    farms = obs.get('farms') or []
    if not isinstance(farms, list) or player >= len(farms):
        return _v33.agent(observation, configuration)

    farm = _m(farms[player])
    tiles = farm.get('tiles') or []
    if not isinstance(tiles, list) or not tiles:
        return _v33.agent(observation, configuration)

    day = int(obs.get('day', 0) or 0)
    hour = int(obs.get('hour', 0) or 0)
    result = dict(_v33.agent(observation, configuration))

    # Grid-derived land state, independent of missing unlocked_quadrants metadata.
    qs = _v33._quadrant_counts(tiles)
    lands = _v33._owned_quadrants(qs)

    # V33.2 originally counted only Q3 livestock. The V19 builder may place
    # pastures anywhere outside NW, so aggregate all pasture/animal capacity into
    # the allocator's livestock district view.
    total_pasture = sum(int(q.get('pasture', 0) or 0) for q in qs.values())
    total_animals = sum(int(q.get('animals', 0) or 0) for q in qs.values())
    districts = {q: dict(v) for q, v in qs.items()}
    districts[3]['pasture'] = total_pasture
    districts[3]['animals'] = total_animals
    stats = {'districts': districts, 'lands': lands}

    # IMPORTANT: execute the replay-driven market allocator for real. This was
    # dead code in V33.2 because v33_industrial.agent never called _market.
    frontier_orders, _ = _v332._market(obs, farm, stats, day, hour)
    result['market'] = frontier_orders[:10]

    # Scale pasture construction, placement, feeding, care and harvesting with
    # herd size instead of inheriting V19's fixed two-hand livestock crew.
    target = _frontier_target(day, lands)
    hands = list(farm.get('hands') or [])
    if target > 0 and hands:
        # ~1 livestock hand per 3 target animals, bounded so crop production
        # retains meaningful labour. 14 animals -> 5 hands; 22 -> 8 hands.
        crew_count = min(len(hands), max(2, min(8, (target + 2) // 3)))
        hand_actions = [list(a) if isinstance(a, list) else ['PASS'] for a in result.get('hands', [])]
        while len(hand_actions) < len(hands):
            hand_actions.append(['PASS'])

        reserved = set()
        health = _v19._farm_health(farm)
        full_service = float(health.get('weed_ratio', 0.0) or 0.0) <= 0.30
        first = max(1, 1 + len(hands) - crew_count)
        for unit_index in range(first, 1 + len(hands)):
            action, _reason = _v19._livestock_action(
                obs, farm, unit_index, reserved, target, full_service
            )
            if action is not None:
                hand_actions[unit_index - 1] = action
        result['hands'] = hand_actions

    return result
