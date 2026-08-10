"""Mine a compact Kaggriculture economic policy from real replay trajectories.

The miner intentionally learns *state targets* and safety thresholds rather than
copying action sequences. Only fit-window trajectories are used for policy
estimation; outer trajectories remain untouched for later validation.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ANIMALS = ("GOOSE", "COW", "SHEEP")
PHASE_DAYS = (5, 10, 15, 20, 25, 29)


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _episode_id(value: Mapping[str, Any]) -> str:
    for container in (value, _m(value.get("metadata")), _m(value.get("info"))):
        for key in ("episodeId", "episode_id", "id"):
            item = container.get(key)
            if item not in (None, ""):
                return str(item)
    return ""


def _find_episode(value: Any, episode_id: str) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        if isinstance(value.get("steps"), list) and value.get("steps"):
            if not episode_id or _episode_id(value) in {"", episode_id}:
                return value
        for child in value.values():
            found = _find_episode(child, episode_id)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_episode(child, episode_id)
            if found is not None:
                return found
    return None


def _load(path: Path, episode_id: str) -> Mapping[str, Any] | None:
    try:
        if path.suffix.lower() == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return _find_episode(data, episode_id)


def _quantile(values: Iterable[float], q: float, default: float = 0.0) -> float:
    vals = sorted(float(v) for v in values)
    if not vals:
        return default
    if len(vals) == 1:
        return vals[0]
    x = (len(vals) - 1) * q
    lo, hi = int(math.floor(x)), int(math.ceil(x))
    if lo == hi:
        return vals[lo]
    w = x - lo
    return vals[lo] * (1 - w) + vals[hi] * w


def _tile_state(observation: Mapping[str, Any], seat: int) -> Dict[str, Any]:
    farms = observation.get("farms") or []
    farm = _m(farms[seat]) if isinstance(farms, list) and seat < len(farms) else {}
    tiles = farm.get("tiles") or []
    crops = Counter()
    animals = Counter()
    usable = occupied = weeds = structures = 0
    backlog = 0
    for row in tiles:
        if not isinstance(row, list):
            continue
        for tile in row:
            if tile == "LOCKED":
                continue
            kind = str(_m(tile).get("kind", "")).upper() if isinstance(tile, Mapping) else ""
            if kind == "LOCKED":
                continue
            usable += 1
            if tile is not None:
                occupied += 1
            if not isinstance(tile, Mapping):
                continue
            td = _m(tile)
            if kind == "WEED":
                weeds += 1
                backlog += 1
            elif kind == "PLANT":
                crop = str(td.get("crop", "")).upper()
                if crop:
                    crops[crop] += 1
                if int(td.get("yield_units", td.get("yield", 0)) or 0) > 0:
                    backlog += 1
                elif not bool(td.get("watered_today", td.get("watered", False))):
                    backlog += 1
            elif kind in {"PASTURE", "COOP"}:
                structures += 1
                animal = str(td.get("animal", "")).upper()
                if animal:
                    animals[animal] += 1
                    if int(td.get("yield_units", td.get("yield", 0)) or 0) > 0:
                        backlog += 1
                    if not bool(td.get("fed_today", td.get("fed", False))):
                        backlog += 1
                    if not bool(td.get("cared_today", td.get("cared", False))):
                        backlog += 1
                    if bool(td.get("fertilizer_available", False)):
                        backlog += 1
    land = farm.get("unlocked_quadrants") or ["NW"]
    return {
        "money": float(farm.get("money", 0) or 0),
        "hands": len(farm.get("hands") or []),
        "land": len(land),
        "usable": usable,
        "occupied": occupied,
        "weed": weeds,
        "weed_ratio": weeds / max(1, usable),
        "backlog": backlog,
        "crop_total": sum(crops.values()),
        "animal_total": sum(animals.values()),
        "structures": structures,
        **{f"crop_{c}": crops[c] for c in CROPS},
        **{f"animal_{a}": animals[a] for a in ANIMALS},
    }


def _count_actions(action: Mapping[str, Any]) -> Counter:
    c = Counter()
    actor_actions = []
    farmer = action.get("farmer")
    if isinstance(farmer, list) and farmer:
        actor_actions.append(farmer)
    for hand in action.get("hands") or []:
        if isinstance(hand, list) and hand:
            actor_actions.append(hand)
    for a in actor_actions:
        op = str(a[0]).upper()
        c[op] += 1
        if op == "PLANT" and len(a) > 1:
            c[f"PLANT_{str(a[1]).upper()}"] += 1
    for mk in action.get("market") or []:
        if not isinstance(mk, list) or not mk:
            continue
        op = str(mk[0]).upper()
        c[op] += 1
        if op == "BUY_ANIMAL" and len(mk) > 1:
            c[f"BUY_ANIMAL_{str(mk[1]).upper()}"] += 1
        if op == "SELL" and len(mk) > 1:
            c[f"SELL_{str(mk[1]).upper()}"] += 1
        if op == "BUY_PRODUCT" and len(mk) > 1:
            c[f"BUY_PRODUCT_{str(mk[1]).upper()}"] += 1
    return c


def _nearest_snapshot(day_states: Dict[int, Dict[str, Any]], target: int) -> Dict[str, Any] | None:
    if target in day_states:
        return day_states[target]
    earlier = [d for d in day_states if d <= target]
    return day_states[max(earlier)] if earlier else None


def _trajectory(episode: Mapping[str, Any], seat: int, row: Mapping[str, str]) -> Dict[str, Any] | None:
    actions = Counter()
    day_states: Dict[int, Dict[str, Any]] = {}
    for step in episode.get("steps") or []:
        if not isinstance(step, list) or seat >= len(step):
            continue
        entry = _m(step[seat])
        observation = _m(entry.get("observation"))
        if observation:
            day = int(observation.get("day", 0) or 0)
            day_states.setdefault(day, _tile_state(observation, seat))
        actions.update(_count_actions(_m(entry.get("action"))))
    if not day_states:
        return None
    reward = float(row.get("reward") or 0)
    opp = float(row.get("opponent_reward") or 0)
    plant_counts = {c: actions[f"PLANT_{c}"] for c in CROPS}
    top_crop = max(CROPS, key=lambda c: plant_counts[c]) if any(plant_counts.values()) else "NONE"
    animal_buys = {a: actions[f"BUY_ANIMAL_{a}"] for a in ANIMALS}
    top_animal = max(ANIMALS, key=lambda a: animal_buys[a]) if any(animal_buys.values()) else "COW"
    return {
        "episode_id": row.get("episode_id") or "",
        "seat": seat,
        "result": row.get("result") or ("win" if reward > opp else "loss" if reward < opp else "tie"),
        "reward": reward,
        "opponent_reward": opp,
        "top_crop": top_crop,
        "top_animal": top_animal,
        "actions": actions,
        "snapshots": {d: _nearest_snapshot(day_states, d) for d in PHASE_DAYS},
    }


def _learn(trajectories: list[Dict[str, Any]]) -> Dict[str, Any]:
    decisive = [t for t in trajectories if t["result"] in {"win", "loss"}]
    winners = [t for t in decisive if t["result"] == "win"]
    if not winners:
        raise RuntimeError("No fit-window winning trajectories were parsed")
    reward_cut = _quantile((t["reward"] for t in winners), 0.75)
    elite = [t for t in winners if t["reward"] >= reward_cut]

    crop_stats = {}
    for crop in CROPS:
        subset = [t for t in decisive if t["top_crop"] == crop]
        wins = sum(t["result"] == "win" for t in subset)
        n = len(subset)
        rate = (wins + 5.0) / (n + 10.0)
        crop_stats[crop] = {"wins": wins, "games": n, "shrunk_winrate": rate}
    eligible = [c for c in CROPS if crop_stats[c]["games"] >= max(20, int(0.02 * len(decisive)))]
    if not eligible:
        eligible = list(CROPS)
    primary_crop = max(eligible, key=lambda c: (crop_stats[c]["shrunk_winrate"], crop_stats[c]["games"]))

    animal_counts = Counter(t["top_animal"] for t in elite)
    primary_animal = animal_counts.most_common(1)[0][0] if animal_counts else "COW"

    phases = {}
    elite_weed = []
    for day in PHASE_DAYS:
        states = [t["snapshots"].get(day) for t in elite]
        states = [s for s in states if s]
        if not states:
            continue
        elite_weed.extend(float(s["weed_ratio"]) for s in states)
        phases[str(day)] = {
            "target_crops": max(1, int(round(_quantile((s["crop_total"] for s in states), 0.50)))),
            "target_animals": max(0, int(round(_quantile((s["animal_total"] for s in states), 0.50)))),
            "target_hands": max(0, int(round(_quantile((s["hands"] for s in states), 0.50)))),
            "target_land": max(1, int(round(_quantile((s["land"] for s in states), 0.50)))),
            "cash_reserve": max(0, int(round(_quantile((s["money"] for s in states), 0.25)))),
            "max_backlog_per_unit": round(_quantile((s["backlog"] / max(1, s["hands"] + 1) for s in states), 0.75), 3),
            "median_weed_ratio": round(_quantile((s["weed_ratio"] for s in states), 0.50), 4),
            "p75_weed_ratio": round(_quantile((s["weed_ratio"] for s in states), 0.75), 4),
        }

    elite_p75 = _quantile(elite_weed, 0.75, 0.04)
    elite_p90 = _quantile(elite_weed, 0.90, 0.08)
    weed_soft = round(max(0.03, min(0.10, elite_p75 + 0.015)), 3)
    weed_hard = round(max(weed_soft + 0.04, min(0.18, elite_p90 + 0.03)), 3)

    def mean_action(group: list[Dict[str, Any]], op: str) -> float:
        return statistics.fmean(t["actions"][op] for t in group) if group else 0.0

    action_comparison = {}
    losers = [t for t in decisive if t["result"] == "loss"]
    for op in ("PLANT", "SELL", "HIRE", "HARVEST", "COLLECT_FERTILIZER", "BUY_ANIMAL", "BUY_LAND", "DIG"):
        action_comparison[op] = {
            "winning_mean": round(mean_action(winners, op), 3),
            "losing_mean": round(mean_action(losers, op), 3),
        }

    return {
        "schema_version": 1,
        "source": "fit-window Kaggle replay trajectories",
        "trajectory_count": len(trajectories),
        "decisive_count": len(decisive),
        "winner_count": len(winners),
        "elite_winner_count": len(elite),
        "elite_reward_cutoff": reward_cut,
        "primary_crop": primary_crop,
        "primary_animal": primary_animal,
        "weed_soft_ratio": weed_soft,
        "weed_hard_ratio": weed_hard,
        "crop_stats": crop_stats,
        "phases": phases,
        "action_comparison": action_comparison,
    }


def mine(corpus: Path, output: Path, max_episodes: int = 0) -> None:
    rows = list(csv.DictReader((corpus / "index.csv").open(encoding="utf-8")))
    fit = [r for r in rows if r.get("window") == "fit"]
    grouped: Dict[tuple[str, str], Dict[int, Mapping[str, str]]] = defaultdict(dict)
    for r in fit:
        grouped[(r.get("episode_id") or "", r.get("source") or "")][int(r.get("seat") or 0)] = r
    items = list(grouped.items())
    if max_episodes > 0:
        items = items[:max_episodes]

    trajectories: list[Dict[str, Any]] = []
    for i, ((episode_id, source), seats) in enumerate(items, 1):
        path = Path(source)
        if not path.exists():
            path = corpus / "episodes" / f"{episode_id}.json.gz"
        if not path.exists():
            continue
        ep = _load(path, episode_id)
        if ep is None:
            continue
        for seat, row in seats.items():
            t = _trajectory(ep, seat, row)
            if t:
                trajectories.append(t)
        if i % 100 == 0 or i == len(items):
            print(json.dumps({"episodes_parsed": i, "trajectories": len(trajectories)}), flush=True)

    policy = _learn(trajectories)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(policy, indent=2), encoding="utf-8")
    print(json.dumps(policy, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", type=Path, default=Path("replay_db"))
    p.add_argument("--output", type=Path, default=Path("artifacts/economic_policy.json"))
    p.add_argument("--max-episodes", type=int, default=0)
    args = p.parse_args()
    mine(args.corpus, args.output, args.max_episodes)
