"""Benchmark V8 against V7 and the frozen strong melon baseline."""
from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

from agents.melon_baseline import agent as melon_baseline
from agents.v7_lifecycle_core import agent as v7_agent
from agents.v8_melon_optimizer import agent as candidate_agent
from scripts.benchmark import GameResult, _run_game, summarize

OPPONENTS = {
    "v7_lifecycle_core": v7_agent,
    "melon_baseline": melon_baseline,
}


def run_benchmark(games_per_seat: int, output: Path | None = None):
    if games_per_seat < 1:
        raise ValueError("games_per_seat must be at least 1")

    all_results: Dict[str, List[GameResult]] = {}
    payload = {
        "candidate": "agents.v8_melon_optimizer",
        "opponents": {},
    }

    for opponent_name, opponent_agent in OPPONENTS.items():
        results: List[GameResult] = []
        for seat in (0, 1):
            for seed in range(games_per_seat):
                result = _run_game(seed, seat, candidate_agent, opponent_agent)
                results.append(result)
                print(
                    f"opponent={opponent_name} seed={seed:04d} seat={seat} "
                    f"v8={result.candidate_reward:.0f} "
                    f"opponent_reward={result.opponent_reward:.0f} "
                    f"delta={result.delta:.0f} status={result.candidate_status}"
                )

        summary = summarize(results)
        seat_mean_delta = {
            str(seat): statistics.fmean(
                result.delta for result in results if result.candidate_seat == seat
            )
            for seat in (0, 1)
        }
        payload["opponents"][opponent_name] = {
            "summary": asdict(summary),
            "seat_mean_delta": seat_mean_delta,
            "games": [asdict(result) for result in results],
        }
        all_results[opponent_name] = results

    combined = [result for results in all_results.values() for result in results]
    combined_summary = summarize(combined)
    payload["combined_summary"] = asdict(combined_summary)
    payload["combined_seat_mean_delta"] = {
        str(seat): statistics.fmean(
            result.delta for result in combined if result.candidate_seat == seat
        )
        for seat in (0, 1)
    }

    print(json.dumps(payload["combined_summary"], indent=2, sort_keys=True))
    print(json.dumps(
        {"combined_seat_mean_delta": payload["combined_seat_mean_delta"]},
        indent=2,
        sort_keys=True,
    ))

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
