"""V33.79: dedicated pasture commissioning over V33.76.

One already-paid livestock worker becomes a pasture commissioner while the herd is
below the replay-derived pasture trajectory. Survival work retains priority: if
any active cow/sheep is unfed, the worker falls back to the normal mixed-livestock
controller. No land, animal-buy, crop, feed-buy, sales or cash-reserve policy is
changed.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents import v33_industrial_v76 as _p

_b = _p._b
_v28 = _p._p._p
_parent_roles = _v28._roles
_parent_unit_action = _v28._unit_action


def _roles(lands: int, hand_count: int):
    roles = list(_parent_roles(lands, hand_count))
    livestock = [i for i, r in enumerate(roles) if r == 'livestock' and i >= 1]
    if livestock:
        roles[livestock[0]] = 'builder'
    return roles


def _unfed_exists(tiles) -> bool:
    for _, t, a in _p._animal_positions(tiles):
        if a in {'COW','SHEEP'} and not bool(t.get('fed_today', False)):
            return True
    return False


def _builder_action(obs: Mapping[str,Any], farm: Mapping[str,Any], p, stats, reserved):
    day = int(obs.get('day',0) or 0)
    lands = int(stats.get('lands',0) or 0)
    tiles = farm.get('tiles') or []
    tc, ts, pasture_target = _p._mixed_targets(day, lands)
    pastures = _p._animal_positions(tiles)
    if day > 14 or len(pastures) >= pasture_target or _unfed_exists(tiles):
        return None
    districts = {3} if lands >= 3 else ({2} if lands >= 2 else {1})
    goals = _b._empty_targets(tiles, districts, reserved)
    r = _b._nearest(tiles, p, goals)
    if r is None:
        return None
    reserved.add(r[1])
    return (["BUILD_PASTURE"] if r[0] == 0 else [r[2]]), 'v79_build_pasture'


def _unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role):
    if role == 'builder':
        action = _builder_action(obs, farm, p, stats, reserved)
        if action is not None:
            return action
        role = 'livestock'
    return _parent_unit_action(obs, farm, idx, p, stats, reserved, seed_budget, role)


_v28._roles = _roles
_v28._unit_action = _unit_action


def agent(observation: Any, configuration: Any=None): return _p.agent(observation, configuration)
def reset_state(): return _p.reset_state()
def reset_telemetry(): return reset_state()
def get_telemetry(clear: bool=False): return _p.get_telemetry(clear=clear)
