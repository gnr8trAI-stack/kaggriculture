"""Extract public-state trajectories and compact winning route medoids."""
from __future__ import annotations

import argparse
import base64
import csv
import gzip
import json
import statistics
import zlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Mapping

CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ANIMALS = ("GOOSE", "COW", "SHEEP")


def _m(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _quadrant(x: int, y: int) -> str:
    if x < 5 and y < 5:
        return "NW"
    if x >= 5 and y < 5:
        return "NE"
    if x < 5 and y >= 5:
        return "SW"
    return "SE"


def _features(observation: Mapping[str, Any], seat: int) -> Dict[str, Any]:
    farms = observation.get("farms") or []
    farm = _m(farms[seat]) if isinstance(farms, list) and seat < len(farms) else {}
    opponent = _m(farms[1 - seat]) if isinstance(farms, list) and len(farms) > 1 else {}
    crops, animals, occupancy, usable = Counter(), Counter(), Counter(), Counter()
    pastures = coops = 0
    tiles = farm.get("tiles") or []
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, tile in enumerate(row):
            q = _quadrant(x, y)
            if tile == "LOCKED":
                continue
            usable[q] += 1
            if tile is not None:
                occupancy[q] += 1
            if isinstance(tile, Mapping):
                kind = str(tile.get("kind", "")).upper()
                if kind == "PLANT":
                    crops[str(tile.get("crop", "")).upper()] += 1
                elif kind == "PASTURE":
                    pastures += 1
                elif kind == "COOP":
                    coops += 1
                animal = str(tile.get("animal", "")).upper()
                if animal:
                    animals[animal] += 1
    market = _m(observation.get("market"))
    prices = _m(market.get("prices"))
    unlocked = farm.get("unlocked_quadrants") or ["NW"]
    out: Dict[str, Any] = {
        "day": int(observation.get("day", 0) or 0),
        "hour": int(observation.get("hour", 0) or 0),
        "money": float(farm.get("money", 0) or 0),
        "opp_money": float(opponent.get("money", 0) or 0),
        "hands": len(farm.get("hands") or []),
        "opp_hands": len(opponent.get("hands") or []),
        "land": tuple(sorted(unlocked)),
        "pastures": pastures,
        "coops": coops,
        "town": tuple(sorted((_m(observation.get("town")).get("unlocked_shops") or []))),
    }
    for q in ("NW", "NE", "SW", "SE"):
        out[f"occ_{q}"] = occupancy[q] / max(1, usable[q])
    for crop in CROPS:
        out[f"crop_{crop}"] = crops[crop]
        out[f"price_{crop}"] = float(prices.get(crop, 0) or 0)
    for animal in ANIMALS:
        out[f"animal_{animal}"] = animals[animal]
    return out


def _action(step_entry: Mapping[str, Any]) -> Mapping[str, Any]:
    return _m(step_entry.get("action"))


def _strategy(final_state: Mapping[str, Any]) -> str:
    animal_total = sum(int(final_state.get(f"animal_{a}", 0) or 0) for a in ANIMALS)
    crop_total = sum(int(final_state.get(f"crop_{c}", 0) or 0) for c in CROPS)
    if animal_total >= 8:
        return "industrial_livestock"
    if len(final_state.get("land") or ()) >= 3 and int(final_state.get("hands", 0) or 0) >= 10:
        return "industrial_crop"
    if crop_total:
        dominant = max(CROPS, key=lambda c: int(final_state.get(f"crop_{c}", 0) or 0))
        share = int(final_state.get(f"crop_{dominant}", 0) or 0) / crop_total
        if share >= 0.65:
            return f"{dominant.lower()}_specialist"
    return "balanced"


def _compress(value: Any) -> str:
    payload = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.b85encode(zlib.compress(payload, 9)).decode("ascii")


def build(corpus: Path, output: Path, max_routes_per_strategy: int = 4) -> None:
    index = list(csv.DictReader((corpus / "index.csv").open(encoding="utf-8")))
    fit_rows = [r for r in index if r.get("window") == "fit" and r.get("result") == "win"]
    candidates: Dict[str, list[Dict[str, Any]]] = defaultdict(list)

    for row in fit_rows:
        path = corpus / "episodes" / f"{row['episode_id']}.json.gz"
        if not path.exists():
            continue
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            episode = json.load(handle)
        seat = int(row["seat"])
        states, actions = [], []
        for step in episode.get("steps") or []:
            if not isinstance(step, list) or seat >= len(step):
                continue
            entry = _m(step[seat])
            observation = _m(entry.get("observation"))
            if not observation:
                continue
            states.append(_features(observation, seat))
            actions.append(_action(entry))
        if not states:
            continue
        strategy = _strategy(states[-1])
        reward = float(row.get("reward") or 0)
        candidates[strategy].append({
            "episode_id": row["episode_id"],
            "strategy": strategy,
            "seat": seat,
            "reward": reward,
            "states": states,
            "actions": actions,
        })

    library = []
    for strategy, routes in candidates.items():
        routes.sort(key=lambda r: r["reward"], reverse=True)
        selected = routes[:max_routes_per_strategy]
        for route in selected:
            library.append({
                "episode_id": route["episode_id"],
                "strategy": route["strategy"],
                "seat": route["seat"],
                "reward": route["reward"],
                "states": route["states"],
                "actions_b85z": _compress(route["actions"]),
            })

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"schema_version": 1, "routes": library}, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"routes": len(library), "strategies": Counter(r["strategy"] for r in library)}, default=dict, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=Path("replay_db"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/route_library.json"))
    parser.add_argument("--max-routes-per-strategy", type=int, default=4)
    args = parser.parse_args()
    build(args.corpus, args.output, args.max_routes_per_strategy)
