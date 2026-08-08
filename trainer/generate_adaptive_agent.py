"""Generate a standalone replay-trained adaptive Kaggriculture submission."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

RUNTIME = r'''
import base64 as _b64
import copy as _copy
import json as _json
import math as _math
import zlib as _zlib

_ROUTE_LIBRARY = __ROUTE_LIBRARY__
_SELECTED_ROUTE = None
_SELECTED_ROUTE_SCORE = None
_LAST_STEP = -1


def _rt_m(v):
    return v if isinstance(v, dict) else {}


def _rt_q(x, y):
    if x < 5 and y < 5: return "NW"
    if x >= 5 and y < 5: return "NE"
    if x < 5 and y >= 5: return "SW"
    return "SE"


def _rt_features(obs):
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms") or []
    farm = _rt_m(farms[player]) if player < len(farms) else {}
    opp = _rt_m(farms[1-player]) if len(farms) > 1 else {}
    crops = {c: 0 for c in ("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON")}
    animals = {a: 0 for a in ("GOOSE","COW","SHEEP")}
    used = {q: 0 for q in ("NW","NE","SW","SE")}
    usable = {q: 0 for q in used}
    pastures = coops = 0
    for y,row in enumerate(farm.get("tiles") or []):
        for x,tile in enumerate(row if isinstance(row,list) else []):
            q = _rt_q(x,y)
            if tile == "LOCKED": continue
            usable[q] += 1
            if tile is not None: used[q] += 1
            if isinstance(tile, dict):
                kind = str(tile.get("kind","")).upper()
                if kind == "PLANT": crops[str(tile.get("crop","")).upper()] = crops.get(str(tile.get("crop","")).upper(),0)+1
                elif kind == "PASTURE": pastures += 1
                elif kind == "COOP": coops += 1
                animal = str(tile.get("animal","")).upper()
                if animal in animals: animals[animal] += 1
    market = _rt_m(obs.get("market")); prices = _rt_m(market.get("prices"))
    out = {
        "day": int(obs.get("day",0) or 0), "hour": int(obs.get("hour",0) or 0),
        "money": float(farm.get("money",0) or 0), "opp_money": float(opp.get("money",0) or 0),
        "hands": len(farm.get("hands") or []), "opp_hands": len(opp.get("hands") or []),
        "land": tuple(sorted(farm.get("unlocked_quadrants") or ["NW"])),
        "pastures": pastures, "coops": coops,
        "town": tuple(sorted((_rt_m(obs.get("town")).get("unlocked_shops") or []))),
    }
    for q in used: out["occ_"+q] = used[q] / max(1, usable[q])
    for c in crops:
        out["crop_"+c] = crops[c]; out["price_"+c] = float(prices.get(c,0) or 0)
    for a in animals: out["animal_"+a] = animals[a]
    return out


def _rt_distance(a, b):
    score = 0.0
    for key, weight, scale in (
        ("money",0.15,10000),("opp_money",0.10,10000),("hands",0.8,10),("opp_hands",0.25,10),
        ("occ_NW",1.0,1),("occ_NE",1.0,1),("occ_SW",1.0,1),("occ_SE",0.6,1),
        ("pastures",0.8,14),("animal_COW",0.8,8),("animal_SHEEP",0.7,6),
        ("crop_WHEAT",0.5,25),("crop_STRAWBERRY",0.6,25),("crop_MELON",0.6,25),
    ):
        score += weight * abs(float(a.get(key,0) or 0)-float(b.get(key,0) or 0))/scale
    if tuple(a.get("land") or ()) != tuple(b.get("land") or ()): score += 1.5
    return score


def _rt_actions(route):
    cached = route.get("_actions")
    if cached is None:
        cached = _json.loads(_zlib.decompress(_b64.b85decode(route["actions_b85z"])).decode("utf-8"))
        route["_actions"] = cached
    return cached


def _rt_select(obs):
    state = _rt_features(obs)
    best = None; best_score = 1e30
    for route in _ROUTE_LIBRARY:
        states = route.get("states") or []
        if not states: continue
        idx = min(int(obs.get("step", state["day"]*24+state["hour"]) or 0), len(states)-1)
        score = _rt_distance(state, states[idx])
        if score < best_score:
            best_score = score; best = route
    return best, best_score


def _rt_safe_repair(obs, action):
    # Preserve route strategy. Only repair immediately dangerous local failures
    # and reorder already-existing sells by current price.
    result = _copy.deepcopy(action) if isinstance(action, dict) else {"farmer":["PASS"],"hands":[],"market":[]}
    market = [list(o) for o in result.get("market",[]) if isinstance(o,list)]
    prices = _rt_m(_rt_m(obs.get("market")).get("prices"))
    sells = [o for o in market if len(o)>=3 and o[0]=="SELL"]
    others = [o for o in market if not (len(o)>=3 and o[0]=="SELL")]
    sells.sort(key=lambda o: float(prices.get(str(o[1]).upper(),0) or 0), reverse=True)
    result["market"] = (sells + others)[:10]
    return result


def agent(observation, configuration=None):
    global _SELECTED_ROUTE, _SELECTED_ROUTE_SCORE, _LAST_STEP
    obs = observation if isinstance(observation, dict) else _as_dict(observation)
    step = int(obs.get("step", int(obs.get("day",0))*24+int(obs.get("hour",0))) or 0)
    if _LAST_STEP >= 0 and step <= _LAST_STEP:
        _SELECTED_ROUTE = None; _SELECTED_ROUTE_SCORE = None
    _LAST_STEP = step

    if _SELECTED_ROUTE is None:
        _SELECTED_ROUTE, _SELECTED_ROUTE_SCORE = _rt_select(obs)
    if _SELECTED_ROUTE is not None:
        states = _SELECTED_ROUTE.get("states") or []
        actions = _rt_actions(_SELECTED_ROUTE)
        if step < len(states) and step < len(actions):
            divergence = _rt_distance(_rt_features(obs), states[step])
            if divergence <= 2.5:
                return _rt_safe_repair(obs, actions[step])
            # Moderate divergence: try a route reselection before planner takeover.
            replacement, score = _rt_select(obs)
            if replacement is not None and score < divergence and score <= 2.5:
                _SELECTED_ROUTE, _SELECTED_ROUTE_SCORE = replacement, score
                replacement_actions = _rt_actions(replacement)
                if step < len(replacement_actions):
                    return _rt_safe_repair(obs, replacement_actions[step])

    return _fallback_agent(obs, configuration)
'''


def generate(route_library: Path, fallback_source: Path, output: Path) -> None:
    library = json.loads(route_library.read_text(encoding="utf-8"))
    routes = library.get("routes") or []
    fallback = fallback_source.read_text(encoding="utf-8")
    fallback = re.sub(r"^from __future__ import annotations\s*$", "", fallback, flags=re.MULTILINE)
    fallback = fallback.replace("def agent(", "def _fallback_agent(", 1)
    runtime = RUNTIME.replace("__ROUTE_LIBRARY__", repr(routes))
    text = '"""Generated adaptive replay-trained Kaggriculture agent."""\nfrom __future__ import annotations\n\n' + fallback + "\n\n" + runtime
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    compile(text, str(output), "exec")
    print(f"wrote {output} ({output.stat().st_size} bytes, routes={len(routes)})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--routes", type=Path, default=Path("artifacts/route_library.json"))
    parser.add_argument("--fallback", type=Path, default=Path("agents/adaptive_agent.py"))
    parser.add_argument("--output", type=Path, default=Path("dist/main.py"))
    args = parser.parse_args()
    generate(args.routes, args.fallback, args.output)
