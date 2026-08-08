"""Mine interpretable strategy archetypes from real Kaggriculture replay trajectories.

This intentionally avoids synthetic clustering.  It classifies trajectories from
observed farm state at days 10/15/20 and ranks archetypes using real fit-window
results with opponent-strength weighting.  The outer window remains untouched.
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
SNAPSHOT_DAYS = (10, 15, 20, 25)
SUPPORTED_ANIMALS = {"COW", "SHEEP", "NONE"}
SUPPORTED_ARCHETYPES = {
    "compact_livestock",
    "mixed_two_district",
    "compact_crop",
    "crop_scale",
}


def _m(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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
            found_id = _episode_id(value)
            if not episode_id or found_id in {"", episode_id}:
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
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                data = json.load(handle)
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
    pos = (len(vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    weight = pos - lo
    return vals[lo] * (1.0 - weight) + vals[hi] * weight


def _family(row: Mapping[str, str]) -> str:
    return str(row.get("submission_id") or row.get("team") or "")


def _score(row: Mapping[str, str]) -> float:
    result = str(row.get("result") or "")
    if result == "win":
        return 1.0
    if result == "tie":
        return 0.5
    return 0.0


def _state(observation: Mapping[str, Any], seat: int) -> Dict[str, Any]:
    farms = observation.get("farms") or []
    farm = _m(farms[seat]) if isinstance(farms, list) and seat < len(farms) else {}
    tiles = farm.get("tiles") or []
    crops = Counter()
    animals = Counter()
    land = list(farm.get("unlocked_quadrants") or ["NW"])
    usable = weeds = occupied = nw_productive = 0
    if isinstance(tiles, list) and tiles:
        half = len(tiles) // 2
        for y, row in enumerate(tiles):
            if not isinstance(row, list):
                continue
            for x, tile in enumerate(row):
                kind = ""
                if tile == "LOCKED":
                    continue
                if isinstance(tile, Mapping):
                    kind = str(tile.get("kind", tile.get("type", ""))).upper()
                    if kind == "LOCKED":
                        continue
                usable += 1
                if tile is not None:
                    occupied += 1
                if kind == "WEED":
                    weeds += 1
                elif kind == "PLANT" and isinstance(tile, Mapping):
                    crop = str(tile.get("crop", "")).upper()
                    if crop in CROPS:
                        crops[crop] += 1
                    if x < half and y < half:
                        nw_productive += 1
                elif kind in {"COOP", "PASTURE"} and isinstance(tile, Mapping):
                    animal = str(tile.get("animal", "")).upper()
                    if animal in ANIMALS:
                        animals[animal] += 1
                    if x < half and y < half:
                        nw_productive += 1
    return {
        "money": float(farm.get("money", 0) or 0),
        "hands": len(farm.get("hands") or []),
        "land": len(land),
        "usable": usable,
        "occupied": occupied,
        "weed_ratio": weeds / max(1, usable),
        "crop_total": sum(crops.values()),
        "animal_total": sum(animals.values()),
        "nw_productive": nw_productive,
        **{f"crop_{name}": int(crops[name]) for name in CROPS},
        **{f"animal_{name}": int(animals[name]) for name in ANIMALS},
    }


def _nearest(day_states: Mapping[int, Dict[str, Any]], target: int) -> Dict[str, Any] | None:
    if target in day_states:
        return day_states[target]
    earlier = [day for day in day_states if day <= target]
    return day_states[max(earlier)] if earlier else None


def _classify(s15: Mapping[str, Any], s20: Mapping[str, Any]) -> str:
    land = max(int(s15.get("land", 1) or 1), int(s20.get("land", 1) or 1))
    animals = max(int(s15.get("animal_total", 0) or 0), int(s20.get("animal_total", 0) or 0))
    crops = max(int(s15.get("crop_total", 0) or 0), int(s20.get("crop_total", 0) or 0))

    if land == 1 and animals >= 2:
        return "compact_livestock"
    if land == 2 and animals >= 2 and crops >= 8:
        return "mixed_two_district"
    if land >= 3 and animals >= 4:
        return "livestock_scale"
    if land >= 2 and animals <= 1 and crops >= 20:
        return "crop_scale"
    if land == 1 and animals <= 1:
        return "compact_crop"
    return "transitional"


def _dominant(snapshot: Mapping[str, Any], prefix: str, names: Iterable[str]) -> str:
    counts = [(int(snapshot.get(f"{prefix}_{name}", 0) or 0), name) for name in names]
    counts.sort(reverse=True)
    return counts[0][1] if counts and counts[0][0] > 0 else "NONE"


def _trajectory(
    episode: Mapping[str, Any],
    seat: int,
    row: Mapping[str, str],
    opponent_family: str,
) -> Dict[str, Any] | None:
    day_last: Dict[int, Dict[str, Any]] = {}
    day_max_hands: Dict[int, int] = defaultdict(int)
    first_land_day: int | None = None
    first_animal_day: int | None = None

    for step in episode.get("steps") or []:
        if not isinstance(step, list) or seat >= len(step):
            continue
        entry = _m(step[seat])
        observation = _m(entry.get("observation"))
        if not observation:
            continue
        day = int(observation.get("day", 0) or 0)
        state = _state(observation, seat)
        day_last[day] = state  # deliberately LAST observation of each day
        day_max_hands[day] = max(day_max_hands[day], int(state["hands"]))
        if first_land_day is None and int(state["land"]) >= 2:
            first_land_day = day
        if first_animal_day is None and int(state["animal_total"]) >= 1:
            first_animal_day = day

    if not day_last:
        return None
    for day, state in day_last.items():
        state["max_hands"] = int(day_max_hands.get(day, state.get("hands", 0)))

    snapshots = {day: _nearest(day_last, day) for day in SNAPSHOT_DAYS}
    s15 = snapshots[15] or {}
    s20 = snapshots[20] or s15
    reward = float(row.get("reward") or 0)
    opp_reward = float(row.get("opponent_reward") or 0)
    archetype = _classify(s15, s20)

    animal_snapshot = s20 if int(s20.get("animal_total", 0) or 0) else s15
    crop_snapshot = s20 if int(s20.get("crop_total", 0) or 0) else s15
    return {
        "episode_id": str(row.get("episode_id") or ""),
        "seat": seat,
        "family": _family(row),
        "opponent_family": opponent_family,
        "result": str(row.get("result") or ("win" if reward > opp_reward else "loss" if reward < opp_reward else "tie")),
        "reward": reward,
        "opponent_reward": opp_reward,
        "archetype": archetype,
        "primary_animal": _dominant(animal_snapshot, "animal", ANIMALS),
        "primary_crop": _dominant(crop_snapshot, "crop", CROPS),
        "first_land_day": first_land_day,
        "first_animal_day": first_animal_day,
        "snapshots": snapshots,
    }


def _family_strength(rows: list[Mapping[str, str]]) -> Dict[str, float]:
    points: Dict[str, float] = defaultdict(float)
    games: Dict[str, int] = defaultdict(int)
    for row in rows:
        if row.get("window") != "fit":
            continue
        family = _family(row)
        if not family:
            continue
        points[family] += _score(row)
        games[family] += 1
    return {
        family: (points[family] + 5.0) / (games[family] + 10.0)
        for family in games
    }


def _profile(group: list[Dict[str, Any]]) -> Dict[str, Any]:
    wins = [t for t in group if t["result"] == "win"]
    if not wins:
        wins = list(group)
    cutoff = _quantile((t["reward"] for t in wins), 0.75, 0.0)
    elite = [t for t in wins if t["reward"] >= cutoff] or wins

    def states(day: int) -> list[Mapping[str, Any]]:
        return [t["snapshots"].get(day) for t in elite if t["snapshots"].get(day)]

    s10, s15, s20 = states(10), states(15), states(20)

    animal_counter = Counter(t["primary_animal"] for t in elite if t["primary_animal"] != "NONE")
    crop_counter = Counter(t["primary_crop"] for t in elite if t["primary_crop"] != "NONE")
    primary_animal = animal_counter.most_common(1)[0][0] if animal_counter else "NONE"
    primary_crop = crop_counter.most_common(1)[0][0] if crop_counter else "NONE"

    first_land = [t["first_land_day"] for t in elite if t["first_land_day"] is not None]
    first_animal = [t["first_animal_day"] for t in elite if t["first_animal_day"] is not None]

    def qstate(items: list[Mapping[str, Any]], key: str, q: float, default: float) -> float:
        return _quantile((float(s.get(key, default) or default) for s in items), q, default)

    return {
        "elite_trajectories": len(elite),
        "elite_reward_cutoff": cutoff,
        "primary_animal": primary_animal,
        "primary_crop": primary_crop,
        "first_land_day_p50": round(_quantile(first_land, 0.50, 99), 2) if first_land else None,
        "first_land_day_p75": round(_quantile(first_land, 0.75, 99), 2) if first_land else None,
        "first_animal_day_p50": round(_quantile(first_animal, 0.50, 99), 2) if first_animal else None,
        "first_animal_day_p75": round(_quantile(first_animal, 0.75, 99), 2) if first_animal else None,
        "target_land_day15": int(round(qstate(s15, "land", 0.50, 1))),
        "target_land_day20": int(round(qstate(s20, "land", 0.50, 1))),
        "target_animals_day15": int(round(qstate(s15, "animal_total", 0.50, 0))),
        "target_animals_day20": int(round(qstate(s20, "animal_total", 0.50, 0))),
        "target_animals_day20_p75": int(round(qstate(s20, "animal_total", 0.75, 0))),
        "target_crops_day15": int(round(qstate(s15, "crop_total", 0.50, 0))),
        "target_crops_day20": int(round(qstate(s20, "crop_total", 0.50, 0))),
        "target_hands_day15": int(round(qstate(s15, "max_hands", 0.50, 0))),
        "target_hands_day20": int(round(qstate(s20, "max_hands", 0.50, 0))),
        "cash_reserve_day10_p25": int(round(qstate(s10, "money", 0.25, 0))),
        "cash_reserve_day15_p25": int(round(qstate(s15, "money", 0.25, 0))),
        "peak_nw_productive_p50": int(round(max(
            qstate(s10, "nw_productive", 0.50, 0),
            qstate(s15, "nw_productive", 0.50, 0),
        ))),
        "weed_ratio_day20_p75": round(qstate(s20, "weed_ratio", 0.75, 0.08), 4),
    }


def mine(corpus: Path, output: Path) -> None:
    rows = list(csv.DictReader((corpus / "index.csv").open(encoding="utf-8")))
    strengths = _family_strength(rows)

    episode_rows: Dict[str, Dict[int, Mapping[str, str]]] = defaultdict(dict)
    for row in rows:
        episode_rows[str(row.get("episode_id") or "")][int(row.get("seat") or 0)] = row

    fit_items: Dict[tuple[str, str], Dict[int, Mapping[str, str]]] = defaultdict(dict)
    for row in rows:
        if row.get("window") == "fit":
            fit_items[(str(row.get("episode_id") or ""), str(row.get("source") or ""))][int(row.get("seat") or 0)] = row

    trajectories: list[Dict[str, Any]] = []
    for index, ((episode_id, source), seats) in enumerate(fit_items.items(), 1):
        path = Path(source)
        if not path.exists():
            path = corpus / "episodes" / f"{episode_id}.json.gz"
        if not path.exists():
            continue
        episode = _load(path, episode_id)
        if episode is None:
            continue
        all_seats = episode_rows.get(episode_id, {})
        for seat, row in seats.items():
            opponent_row = all_seats.get(1 - seat, {})
            trajectory = _trajectory(episode, seat, row, _family(opponent_row))
            if trajectory:
                trajectories.append(trajectory)
        if index % 100 == 0 or index == len(fit_items):
            print(json.dumps({"episodes_parsed": index, "trajectories": len(trajectories)}), flush=True)

    if not trajectories:
        raise RuntimeError("No fit-window trajectories parsed")

    by_arch: Dict[str, list[Dict[str, Any]]] = defaultdict(list)
    for t in trajectories:
        by_arch[t["archetype"]].append(t)

    min_sample = max(30, int(round(len(trajectories) * 0.01)))
    archetypes: Dict[str, Any] = {}
    for name, group in sorted(by_arch.items()):
        total_weight = weighted_points = 0.0
        rewards = []
        for t in group:
            opponent_strength = strengths.get(t["opponent_family"], 0.5)
            weight = 0.5 + opponent_strength
            point = 1.0 if t["result"] == "win" else 0.5 if t["result"] == "tie" else 0.0
            total_weight += weight
            weighted_points += weight * point
            rewards.append(float(t["reward"]))
        weighted_rate = weighted_points / max(1e-9, total_weight)
        shrunk = (weighted_points + 8.0 * 0.5) / (total_weight + 8.0)
        profile = _profile(group)
        supported = (
            name in SUPPORTED_ARCHETYPES
            and profile["primary_animal"] in SUPPORTED_ANIMALS
            and profile["target_land_day20"] <= 2
        )
        archetypes[name] = {
            "trajectories": len(group),
            "wins": sum(t["result"] == "win" for t in group),
            "losses": sum(t["result"] == "loss" for t in group),
            "ties": sum(t["result"] == "tie" for t in group),
            "opponent_strength_weighted_winrate": round(weighted_rate, 6),
            "shrunk_weighted_winrate": round(shrunk, 6),
            "median_reward": round(statistics.median(rewards), 2),
            "p10_reward": round(_quantile(rewards, 0.10), 2),
            "p90_reward": round(_quantile(rewards, 0.90), 2),
            "supported_by_v20_executor": supported,
            "profile": profile,
        }

    eligible = [
        (stats["shrunk_weighted_winrate"], stats["median_reward"], stats["trajectories"], name)
        for name, stats in archetypes.items()
        if stats["trajectories"] >= min_sample and stats["supported_by_v20_executor"]
    ]
    if not eligible:
        raise RuntimeError(
            f"No supported archetype has at least {min_sample} fit trajectories; "
            "V20 refuses to fabricate a policy."
        )
    eligible.sort(reverse=True)
    selected_name = eligible[0][3]
    selected = archetypes[selected_name]

    report = {
        "schema_version": 1,
        "source": "real fit-window Kaggle replay trajectories",
        "trajectory_count": len(trajectories),
        "minimum_archetype_sample": min_sample,
        "family_strength_count": len(strengths),
        "selection_rule": (
            "highest shrunk opponent-strength-weighted win rate among interpretable "
            "archetypes executable by the conservative V20 controller; median reward "
            "and sample size break ties"
        ),
        "selected_archetype": selected_name,
        "selected_profile": selected["profile"],
        "selected_statistics": {k: v for k, v in selected.items() if k != "profile"},
        "archetypes": archetypes,
        "outer_window_used": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=Path("replay_db"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/strategy_oracle.json"))
    args = parser.parse_args()
    mine(args.corpus, args.output)
