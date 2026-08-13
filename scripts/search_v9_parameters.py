"""Search V9 portfolio parameters against the frozen strong melon baseline."""
from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

from agents import v9_portfolio_optimizer as v9
from agents.melon_baseline import agent as melon_agent
from scripts.benchmark import GameResult, _run_game, summarize


def evaluate_config(config: Dict[str, int], seeds_per_seat: int) -> Dict[str, object]:
    v9.MELON_SHARE = config["melon_share"]
    v9.TARGET_HANDS = config["target_hands"]
    v9.MELON_STOP_DAY = config["melon_stop_day"]
    v9.TOMATO_STOP_DAY = config["tomato_stop_day"]

    results: List[GameResult] = []
    started = time.perf_counter()
    for seat in (0, 1):
        for seed in range(seeds_per_seat):
            results.append(_run_game(seed, seat, v9.agent, melon_agent))
    elapsed = time.perf_counter() - started
    summary = summarize(results)
    seat_mean = {
        str(seat): statistics.fmean(r.delta for r in results if r.candidate_seat == seat)
        for seat in (0, 1)
    }
    return {
        "config": dict(config),
        "summary": asdict(summary),
        "seat_mean_delta": seat_mean,
        "runtime_seconds": elapsed,
    }


def run_search(seeds_per_seat: int, output: Path | None = None):
    configurations = []
    for melon_share in (30, 40, 50, 60, 70, 80, 90, 100):
        for target_hands in (4, 5, 6):
            for melon_stop_day in (14, 15, 16):
                tomato_stop_day = min(19, melon_stop_day + 3)
                configurations.append({
                    "melon_share": melon_share,
                    "target_hands": target_hands,
                    "melon_stop_day": melon_stop_day,
                    "tomato_stop_day": tomato_stop_day,
                })

    evaluations = []
    for index, config in enumerate(configurations, 1):
        result = evaluate_config(config, seeds_per_seat)
        evaluations.append(result)
        summary = result["summary"]
        print(
            f"[{index:02d}/{len(configurations):02d}] {config} "
            f"mean={summary['mean_delta']:.1f} min={summary['min_delta']:.1f} "
            f"wins={summary['wins']}/{summary['games']} invalid={summary['invalid_or_error_games']}"
        )

    evaluations.sort(
        key=lambda item: (
            item["summary"]["invalid_or_error_games"] == 0,
            item["summary"]["mean_delta"],
            item["summary"]["min_delta"],
        ),
        reverse=True,
    )
    payload = {
        "opponent": "agents.melon_baseline",
        "seeds_per_seat": seeds_per_seat,
        "configurations": len(configurations),
        "best": evaluations[0],
        "top_10": evaluations[:10],
        "all": evaluations,
    }
    print("BEST")
    print(json.dumps(payload["best"], indent=2, sort_keys=True))
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote {output}")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds-per-seat", type=int, default=2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run_search(args.seeds_per_seat, args.output)
