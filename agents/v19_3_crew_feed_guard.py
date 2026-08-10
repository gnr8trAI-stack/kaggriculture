"""V19.3 staged challenger: crew-only carried-feed accounting.

V19.1 counted WHEAT carried by every worker as globally available feed. That is
not valid for V19's role split: only the final two livestock hands execute FEED,
while crop workers can carry wheat that the livestock crew cannot use without a
shed transfer. V19.3 therefore subtracts only shed wheat plus wheat already held
by the actual livestock crew from the feed reserve target.

All V19 expansion, livestock count, routing, crop policy, hiring limits and cash
thresholds remain unchanged. This candidate is staged for the next live quota;
it must not be submitted on 2026-08-09 after the five-slot budget is exhausted.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple

from agents import v19_livestock_compound as _v19


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _livestock_crew_indices(farm: Mapping[str, Any], active_count: int, target_cows: int, pasture_count: int) -> List[int]:
    hands=list(farm.get("hands") or [])
    crew_count=min(2,len(hands)) if (active_count or target_cows>0 or pasture_count>0) else 0
    return list(range(1+len(hands)-crew_count,1+len(hands))) if crew_count else []


def _inject_market_orders(
    base_orders: Sequence[Any], *, expansion_eligible: bool, land_injected: bool,
    obs: Mapping[str, Any], farm: Mapping[str, Any], target_cows: int,
) -> Tuple[List[List[Any]], Dict[str, int]]:
    private=_m(obs.get("private")); shed=_m(private.get("shed"))
    inventories=private.get("inventories",[])
    tiles=farm.get("tiles") or []; hands=list(farm.get("hands") or [])
    active_count=len(_v19._active_cows(tiles)); cow_count=_v19._cow_count(obs,farm)
    empty_pastures=len(_v19._empty_pastures(tiles)); pasture_count=len(_v19._pastures(tiles))

    clean=[]
    for raw in base_orders:
        if not isinstance(raw,list) or not raw: continue
        if str(raw[0]).upper() in {"BUY_LAND","BUY_ANIMAL"}: continue
        clean.append(list(raw))

    critical=[]
    if expansion_eligible and land_injected: critical.append(["BUY_LAND"])

    # Only feed physically in the shed or already on a livestock worker is
    # immediately usable by V19's livestock sidecar.
    usable_wheat=int(shed.get("WHEAT",0) or 0)
    crew_indices=_livestock_crew_indices(farm,active_count,target_cows,pasture_count)
    if isinstance(inventories,list):
        for idx in crew_indices:
            if 0 <= idx < len(inventories):
                usable_wheat += int(_m(inventories[idx]).get("WHEAT",0) or 0)
    feed_target=active_count*_v19.FEED_BUFFER_PER_COW
    if active_count>0 and usable_wheat<feed_target:
        critical.append(["BUY_PRODUCT","WHEAT",feed_target-usable_wheat])

    need=min(empty_pastures,max(0,target_cows-cow_count))
    if need>0:
        affordable=max(0,int((float(farm.get("money",0) or 0)-1000)//_v19.ANIMAL_COST))
        buy=min(need,affordable)
        if buy>0: critical.append(["BUY_ANIMAL",_v19.ANIMAL,buy])

    hires_in_clean=sum(1 for o in clean if o[:1]==["HIRE"])
    desired=min(_v19.MAX_HANDS_WITH_COWS,_v19.MIN_HANDS_WITH_COWS if (active_count or target_cows>0) else len(hands))
    extra=max(0,desired-len(hands)-hires_in_clean)
    critical.extend([["HIRE"] for _ in range(extra)])

    return (critical+clean)[:10],{
        "wheat_bought":sum(int(o[2]) for o in critical if o[:2]==["BUY_PRODUCT","WHEAT"]),
        "cows_bought":sum(int(o[2]) for o in critical if o[:2]==["BUY_ANIMAL",_v19.ANIMAL]),
        "extra_hires":extra,
    }


_v19._inject_market_orders=_inject_market_orders


def reset_state() -> None: _v19.reset_state()
def reset_telemetry() -> None: _v19.reset_telemetry()
def get_telemetry(clear: bool=False): return _v19.get_telemetry(clear=clear)
def agent(observation: Any, configuration: Any=None): return _v19.agent(observation,configuration)
