"""V33.70 cross-district crop-worker overflow.

Single mechanism over V33.66: when a Q1/Q2 crop worker has no actionable task in
its assigned district, let that already-paid worker service or commission the
other owned crop district before idling. No land, labour, livestock, seed-budget,
market, crop-selection, feed, sales, or Q4 policy changes.

Rationale: V33.66 repeatedly peaks near 59 productive tiles while carrying about
61 idle unlocked tiles with 15 hands. V33.68 demand gating and V33.69 seed-order
priority were behavioral no-ops, so the next binding-constraint test moves below
capital allocation to worker/task utilization on capacity we already own.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v66 as _p

_b = _p._b
_v28 = _p._p._p
_parent_unit_action = _v28._unit_action


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    action, tag = _parent_unit_action(
        obs, farm, idx, p, stats, reserved, seed_budget, role
    )
    if tag != "idle" or role not in {"q1", "q2"}:
        return action, tag

    lands = int(stats.get("lands", 0) or 0)
    if lands < 2:
        return action, tag

    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    tiles = farm.get("tiles") or []
    other = {2} if role == "q1" else {1}

    # First help with already-existing maintenance/harvest work in the other
    # crop district. This consumes no additional capital and is the strongest
    # form of productive overflow.
    tasks = _v28._v25._v24._v23._tile_tasks(tiles, other, reserved)
    task = _b._best_task(tiles, p, tasks, reserved)
    if task is not None:
        return task[0], "v70_overflow_" + str(task[1])

    # If the other district has empty owned capacity, commission it using only
    # seed inventory that the unchanged parent allocator already bought.
    if day <= 27 and hour <= 18:
        choices = []
        for g in _b._empty_targets(tiles, other, reserved):
            crop = _v28._crop_for(day, next(iter(other)), obs)
            if seed_budget.get(crop, 0) <= 0:
                continue
            rr = _b._route(tiles, p, g)
            if rr is not None:
                choices.append((rr[0], g[1], g[0], g, crop, rr[1]))
        if choices:
            choices.sort()
            dist, _, _, target, crop, first = choices[0]
            reserved.add(target)
            if dist == 0:
                seed_budget[crop] -= 1
                return ["PLANT", crop], "v70_overflow_plant_" + crop.lower()
            return [first], "v70_overflow_move_to_plant"

    return action, tag


# Patch the exact global consumed by V33.28's agent path. V33.66's allocator,
# three-land discipline, and all other inherited mechanisms remain unchanged.
_v28._unit_action = _unit_action


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)
