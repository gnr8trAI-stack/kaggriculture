"""V33.52 four-quadrant capital allocator with restored Q2 commissioning.

V33.51 introduced a single authority for Q3/Q4 land commissioning but
accidentally removed the inherited Q2 BUY_LAND order before replacing it.  The
24-game telemetry made the failure unambiguous: median peak land stayed at one
while Q1 accumulated enough cash to expand.  This revision repairs the capital
allocator boundary rather than changing crop/livestock thresholds.

Architecture remains V33 industrial and independent of V19/V32:
* V50 allocator owns the Q1 -> Q2 bootstrap packet that has already been
  mechanics-tested in the branch.
* V51 autonomous allocator owns Q3/Q4, operating reserve and commissioning.
* Exactly one allocator owns land at each farm stage, preventing competing
  BUY_LAND decisions or same-packet double-spend.
* V19.2 remains reference control only and is not imported.
"""
from __future__ import annotations
from typing import Any
from agents import v33_industrial_v51 as _p

_b = _p._b
_v51_allocator = _p._capital_allocator
_v50_allocator = _p._parent_allocator


def _capital_allocator(obs, farm, stats):
    lands = max(1, int(stats.get("lands", 1) or 1))

    # V51's regression was caused by unconditional removal of BUY_LAND followed
    # by replacement rules only for lands==2/3.  At one land, hand authority to
    # the proven V50 bootstrap allocator.  It emits Q2 together with bootstrap
    # working capital at dawn and its upstream labour discipline keeps the
    # market packet within the ten-order engine limit.
    if lands == 1:
        orders, meta = _v50_allocator(obs, farm, stats)
        meta = dict(meta)
        if any(isinstance(o, list) and o and o[0] == "BUY_LAND" for o in orders):
            meta["district_commission_v52"] = {
                "district": 2,
                "authority": "v50_bootstrap",
                "bank": round(float(farm.get("money", 0) or 0), 1),
            }
        else:
            meta["q2_wait_v52"] = "bootstrap_allocator_not_ready"
        return orders[:10], meta

    # Q3/Q4 remain under V51's cash-backed autonomous commissioning allocator.
    orders, meta = _v51_allocator(obs, farm, stats)
    meta = dict(meta)
    meta["land_authority_v52"] = "v51_autonomous_q3_q4"
    return orders[:10], meta


_b._capital_allocator = _capital_allocator


def agent(observation: Any, configuration: Any = None):
    return _p.agent(observation, configuration)


def reset_state():
    return _p.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _p.get_telemetry(clear=clear)


def industrial_peaks():
    return _p.industrial_peaks()
