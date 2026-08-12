"""V33.42 isolated three-land labour right-sizing.

Single mechanism over V33.39: once three or more quadrants are owned, cap
recurring daily HIRE orders at 11 hands instead of the parent's 14. Land,
animals, feed, crop capital, sales, routing and terminal realization are
otherwise unchanged. This tests whether the D18-D20 cash trough is driven by
marginal labour whose recurring Fibonacci wage exceeds its realized output.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v39 as _p

_b = _p._b
_parent_allocator = _p._capital_allocator


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_allocator(obs, farm, stats)
    lands = max(1, int(stats.get("lands", 1) or 1))
    if lands < 3:
        return orders, meta

    hands = list(farm.get("hands") or [])
    allowed_hires = max(0, 11 - len(hands))
    kept = []
    hires_kept = 0
    for order in orders:
        if not isinstance(order, list) or not order:
            continue
        op = str(order[0]).upper()
        if op == "HIRE":
            if hires_kept >= allowed_hires:
                continue
            hires_kept += 1
        kept.append(order)

    if isinstance(meta, dict):
        meta = dict(meta)
        meta["labour_cap_3land"] = 11
        meta["hires"] = hires_kept
        try:
            meta["hire_cost"] = _p._hire_cost(len(hands), hires_kept) if hires_kept else 0
        except Exception:
            pass
    return kept[:10], meta


_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)
