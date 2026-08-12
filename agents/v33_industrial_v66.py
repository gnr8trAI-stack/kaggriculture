"""V33.66 utilization-gated third district.

Single economic mechanism over V33.65: retain its three-district cap, but delay
the Q2 -> Q3 land purchase until the first two districts demonstrate stronger
productive density and cash coverage. V33.65 improved median reward materially
while still carrying ~61 peak idle tiles and a 43k lower tail. The hypothesis is
that marginal Q3 capex is beneficial only after Q1/Q2 are dense enough to fund
commissioning without creating another idle-capacity trough.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v65 as _p

_b = _p._b
_parent_alloc = _p._capital_allocator


def _capital_allocator(obs, farm, stats):
    orders, meta = _parent_alloc(obs, farm, stats)
    meta = dict(meta)
    lands = max(1, int(stats.get("lands", 1) or 1))
    if lands == 2:
        productive = int(stats.get("productive", 0) or 0)
        money = float(farm.get("money", 0) or 0)
        q1 = (stats.get("districts") or {}).get(1, {})
        q2 = (stats.get("districts") or {}).get(2, {})
        q12_prod = int(q1.get("productive", 0) or 0) + int(q2.get("productive", 0) or 0)
        ready = productive >= 30 and q12_prod >= 30 and money >= 9000
        if not ready:
            filtered = []
            blocked = 0
            for order in orders:
                if isinstance(order, list) and order and str(order[0]).upper() == "BUY_LAND":
                    blocked += 1
                    continue
                filtered.append(list(order) if isinstance(order, list) else order)
            meta["v66_q3_gate_block"] = blocked
            return filtered[:10], meta
    meta["v66_q3_gate_block"] = 0
    return orders[:10], meta


# Patch the exact allocator consumed by V33.28's agent path, while preserving
# V33.65's Q4 suppression and every other economic/operational rule.
_p._capital_allocator = _capital_allocator
_p._p._capital_allocator = _capital_allocator
_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)
