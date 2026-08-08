"""Generate one replay-derived V20 challenger by parameterizing the V19 executor."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def _clamp(value: float, low: int, high: int) -> int:
    return max(low, min(high, int(round(value))))


def _replace_constant(source: str, name: str, value: Any) -> str:
    rendered = repr(value)
    pattern = rf"(?m)^{re.escape(name)}\s*=\s*.*$"
    updated, count = re.subn(pattern, f"{name} = {rendered}", source, count=1)
    if count != 1:
        raise RuntimeError(f"Could not patch constant {name}")
    return updated


def generate(oracle_path: Path, base_path: Path, output: Path) -> None:
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    profile = oracle["selected_profile"]
    archetype = str(oracle["selected_archetype"])
    animal = str(profile.get("primary_animal") or "NONE").upper()

    if animal not in {"NONE", "COW", "SHEEP"}:
        raise RuntimeError(
            f"Selected archetype requires unsupported animal {animal}; "
            "V20 refuses to silently substitute another livestock strategy."
        )

    target_land = _clamp(float(profile.get("target_land_day20", 1) or 1), 1, 2)
    first_land = profile.get("first_land_day_p50")
    land_p75 = profile.get("first_land_day_p75")
    if target_land >= 2:
        expand_min = _clamp((first_land if first_land is not None else 11) - 1, 6, 16)
        expand_max = _clamp((land_p75 if land_p75 is not None else expand_min + 5) + 2, expand_min + 2, 22)
    else:
        expand_min = 99
        expand_max = 99

    animal15 = _clamp(float(profile.get("target_animals_day15", 0) or 0), 0, 3)
    animal20 = _clamp(float(profile.get("target_animals_day20_p75", profile.get("target_animals_day20", 0)) or 0), 0, 6)
    if animal == "NONE":
        animal15 = 0
        animal20 = 0
        runtime_animal = "COW"  # inert because both targets are zero
        animal_cost = 400
    else:
        runtime_animal = animal
        animal_cost = 400 if animal == "COW" else 500
    max_animals = max(animal15, animal20)

    first_animal = profile.get("first_animal_day_p75")
    start_animals_max_day = _clamp(
        (first_animal if first_animal is not None else 15) + 3,
        10,
        21,
    )

    cash10 = max(0, int(profile.get("cash_reserve_day10_p25", 0) or 0))
    cash15 = max(0, int(profile.get("cash_reserve_day15_p25", 0) or 0))
    post_land_reserve = _clamp(max(1200, min(3500, cash10)), 1200, 3500)
    min_cash_initial = max(900, min(4000, cash15 + max(1, animal15) * animal_cost))
    min_cash_max = max(min_cash_initial, min(6000, cash15 + max(1, max_animals) * animal_cost))

    target_hands15 = _clamp(float(profile.get("target_hands_day15", 5) or 5), 0, 7)
    target_hands20 = _clamp(float(profile.get("target_hands_day20", target_hands15) or target_hands15), 0, 7)
    min_hands = max(5, target_hands15) if max_animals > 0 else 5
    max_hands = max(min_hands, min(7, max(6, target_hands20))) if max_animals > 0 else 7

    peak_nw = _clamp(float(profile.get("peak_nw_productive_p50", 20) or 20), 15, 24)
    weed_p75 = float(profile.get("weed_ratio_day20_p75", 0.08) or 0.08)
    weed_growth = max(0.06, min(0.16, weed_p75 * 1.15 + 0.01))
    weed_service = max(0.12, min(0.25, weed_growth + 0.07))

    source = base_path.read_text(encoding="utf-8")
    patches = {
        "POST_LAND_CASH_RESERVE": post_land_reserve,
        "MIN_PEAK_NW_PRODUCTIVE": peak_nw,
        "EXPAND_MIN_DAY": expand_min,
        "EXPAND_MAX_DAY": expand_max,
        "ANIMAL": runtime_animal,
        "ANIMAL_COST": animal_cost,
        "INITIAL_COW_TARGET": animal15,
        "MAX_COW_TARGET": max_animals,
        "START_COWS_MAX_DAY": start_animals_max_day,
        "MIN_CASH_FOR_TWO": min_cash_initial,
        "MIN_CASH_FOR_FOUR": min_cash_max,
        "MIN_HANDS_WITH_COWS": min_hands,
        "MAX_HANDS_WITH_COWS": max_hands,
        "MAX_WEED_RATIO_FOR_GROWTH": round(weed_growth, 4),
        "MAX_WEED_RATIO_FOR_FULL_SERVICE": round(weed_service, 4),
    }
    for name, value in patches.items():
        source = _replace_constant(source, name, value)

    provenance = {
        "selected_archetype": archetype,
        "selected_statistics": oracle.get("selected_statistics", {}),
        "selected_profile": profile,
        "patched_executor_constants": patches,
    }
    source = (
        "# V20 REPLAY-ORACLE GENERATED CANDIDATE\n"
        "# Generated only from fit-window real Kaggle replay trajectories.\n"
        f"# Oracle profile: {json.dumps(provenance, sort_keys=True)}\n"
        + source
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(source, encoding="utf-8")
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--base", type=Path, default=Path("agents/v19_livestock_compound.py"))
    parser.add_argument("--output", type=Path, default=Path("dist/v20_candidate.py"))
    args = parser.parse_args()
    generate(args.oracle, args.base, args.output)
