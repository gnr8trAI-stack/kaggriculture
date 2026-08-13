"""V33.73 forced Q3 feed-strip commissioning.

Single economic mechanism over V33.66: the already-paid Q3 feed worker may
commission an empty Q3 crop tile before routine non-urgent crop maintenance.
Urgent harvest/water work retains priority. No land, labour, animal, feed,
seed-purchase, crop-choice, sales, or Q4 policy changes.

Rationale: V33.66 reaches three lands but leaves about 11 Q3 cells idle at D20
while running only ~6 Q3 plants. V33.72 showed that adding another feed role is
a no-op, so the bottleneck is not role count. This tests whether task priority
inside the existing feed role is preventing already-funded Q3 crop capacity
from being commissioned.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v66 as _p

_b = _p._b
_v28 = _p._p._p
_parent_unit_action = _v28._unit_action


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    if role == "feed" and int(stats.get("lands", 0) or 0) >= 3:
        day = int(obs.get("day", 0) or 0)
        hour = int(obs.get("hour", 0) or 0)
        if 10 <= day <= 24 and hour <= 12 and int(seed_budget.get("WHEAT", 0) or 0) > 0:
            tiles = farm.get("tiles") or []
            q3 = (stats.get("districts") or {}).get(3, {})
            idle = int(q3.get("idle", 0) or 0)

            # Never trade crop survival or a ready harvest for commissioning.
            urgent = [
                t for t in _v28._v25._v24._v23._tile_tasks(tiles, {3}, reserved)
                if int(t[0]) == 0
            ]
            if idle >= 4 and not urgent:
                choices = []
                for g in _b._empty_targets(tiles, {3}, reserved):
                    rr = _b._route(tiles, p, g)
                    if rr is not None:
                        choices.append((rr[0], g[1], g[0], g, rr[1]))
                if choices:
                    choices.sort()
                    dist, _, _, target, first = choices[0]
                    reserved.add(target)
                    if dist == 0:
                        seed_budget["WHEAT"] -= 1
                        return ["PLANT", "WHEAT"], "v73_q3_commission_plant"
                    return [first], "v73_q3_commission_move"

    return _parent_unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role)


# Patch the exact unit-action global consumed by V33.28's active agent path.
_v28._unit_action = _unit_action


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)
