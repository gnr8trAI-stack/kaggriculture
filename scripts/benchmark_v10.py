"""Benchmark V10 market front-runner against strong known policies."""
from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

from agents.melon_baseline import agent as melon_baseline
from agents.v7_lifecycle_core import agent as v7_agent
from agents.v8_melon_optimizer import agent as v8_agent
from agents.v10_market_front_runner import agent as candidate_agent
from scripts.benchmark import GameResult, _run_game, summarize

OPPONENTS = {
    "melon_baseline": melon_baseline,
    "v8_melon_optimizer": v8_agent,
    "v7_lifecycle_core": v7_agent,
}


def run_benchmark(games_per_seat: int, output: Path | None = None):
    if games_per_seat < 1:
        raise ValueError("games_per_seat must be at least 1")

    started = time.perf_counter()
    all_results: List[GameResult] = []
    by_opponent: Dict[str, dict] = {}

    for opponent_name, opponent_agent in OPPONENTS.items():
        results: List[GameResult] = []
        opponent_started = time.perf_counter()
        for seat in (0, 1):
            for seed in range(games_per_seat):
                result = _run_game(seed, seat, candidate_agent, opponent_agent)
                results.append(result)
                all_results.append(result)
                print(
                    f"opponent={opponent_name} seed={seed:04d} seat={seat} "
                    f"v10={result.candidate_reward:.0f} "
                    f"opponent_reward={result.opponent_reward:.0f} "
                    f"delta={result.delta:+.0f} status={result.candidate_status}"
                )

        summary = summarize(results)
        seat_mean_delta = {
            str(seat): statistics.fmean(
                r.delta for r in results if r.candidate_seat == seat
            )
            for seat in (0, 1)
        }
        by_opponent[opponent_name] = {
            "summary": asdict(summary),
            "seat_mean_delta": seat_mean_delta,
            "runtime_seconds": time.perf_counter() - opponent_started,
            "games": [asdict(result) for result in results],
        }

    overall = summarize(all_results)
    overall_seat_mean_delta = {
        str(seat): statistics.fmean(
            r.delta for r in all_results if r.candidate_seat == seat
        )
        for seat in (0, 1)
    }
    payload = {
        "candidate": "agents.v10_market_front_runner",
        "opponents": list(OPPONENTS),
        "summary": asdict(overall),
        "seat_mean_delta": overall_seat_mean_delta,
        "by_opponent": by_opponent,
        "runtime_seconds": time.perf_counter() - started,
    }

    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    print(json.dumps(payload["seat_mean_delta"], indent=2, sort_keys=True))
    print(
        json.dumps(
            {
                name: data["summary"]
                for name, data in by_opponent.items()
            },
            indent=2,
            sort_keys=True,
        )
    )

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote {output}")

    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--games-per-seat", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run_benchmark(args.games_per_seat, args.output)
