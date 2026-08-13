"""V33.71 planting-priority crop commissioning.

Single mechanism over V33.66: while an owned Q1/Q2 district remains materially
under-utilized, let its existing crop workers use the first six hours of the day
to commission empty owned tiles before routine non-urgent maintenance. Urgent
harvest/water tasks retain priority. No land, labour, livestock, seed-budget,
market, crop-selection, feed, sales, or Q4 policy changes.

V33.70 proved cross-district overflow was a no-op because crop workers never
reached idle despite ~63 idle owned tiles. This tests whether maintenance-first
task ordering, rather than worker count or seed supply, is starving new-tile
commissioning.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v66 as _p

_b = _p._b
_v28 = _p._p._p
_parent_unit_action = _v28._unit_action


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    if role in {"q1", "q2"}:
        day = int(obs.get("day", 0) or 0)
        hour = int(obs.get("hour", 0) or 0)
        lands = int(stats.get("lands", 0) or 0)
        district = 1 if role == "q1" else 2
        if lands >= district and 7 <= day <= 22 and hour <= 6:
            tiles = farm.get("tiles") or []
            q = (stats.get("districts") or {}).get(district, {})
            unlocked = int(q.get("unlocked", 0) or 0)
            productive = int(q.get("productive", 0) or 0)
            utilization = productive / max(1, unlocked)

            # Never trade urgent crop survival/realization for expansion.
            urgent = [t for t in _v28._v25._v24._v23._tile_tasks(tiles, {district}, reserved)
                      if int(t[0]) == 0]
            if utilization < 0.72 and not urgent:
                choices = []
                for g in _b._empty_targets(tiles, {district}, reserved):
                    crop = _v28._crop_for(day, district, obs)
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
                        return ["PLANT", crop], "v71_commission_plant_" + crop.lower()
                    return [first], "v71_commission_move"

    return _parent_unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role)


_v28._unit_action = _unit_action


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)
