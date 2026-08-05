"""Benchmark V11 against the strongest known repository policies."""
import argparse
import json
import statistics
import time
from dataclasses import asdict
from pathlib import Path

from agents.melon_baseline import agent as melon_baseline
from agents.v7_lifecycle_core import agent as v7_agent
from agents.v10_market_front_runner import agent as v10_agent
from agents.v11_agent import agent as candidate_agent
from scripts.benchmark import _run_game, summarize

OPPONENTS = {
    "v10_market_front_runner": v10_agent,
    "melon_baseline": melon_baseline,
    "v7_lifecycle_core": v7_agent,
}


def run_benchmark(games_per_seat: int, seed_start: int = 70000, output: Path = None):
    if games_per_seat < 1:
        raise ValueError("games_per_seat must be at least 1")
    started = time.perf_counter()
    all_results = []
    by_opponent = {}

    for opponent_name, opponent_agent in OPPONENTS.items():
        results = []
        opponent_started = time.perf_counter()
        for seat in (0, 1):
            for offset in range(games_per_seat):
                seed = seed_start + offset
                result = _run_game(seed, seat, candidate_agent, opponent_agent)
                results.append(result)
                all_results.append(result)
                print(
                    f"opponent={opponent_name} seed={seed} seat={seat} "
                    f"v11={result.candidate_reward:.0f} opponent_reward={result.opponent_reward:.0f} "
                    f"delta={result.delta:+.0f} status={result.candidate_status}"
                )
        summary = summarize(results)
        by_opponent[opponent_name] = {
            "summary": asdict(summary),
            "seat_mean_delta": {
                str(seat): statistics.fmean(r.delta for r in results if r.candidate_seat == seat)
                for seat in (0, 1)
            },
            "runtime_seconds": time.perf_counter() - opponent_started,
            "games": [asdict(result) for result in results],
        }

    overall = summarize(all_results)
    payload = {
        "candidate": "agents.v11_agent",
        "summary": asdict(overall),
        "seat_mean_delta": {
            str(seat): statistics.fmean(r.delta for r in all_results if r.candidate_seat == seat)
            for seat in (0, 1)
        },
        "by_opponent": by_opponent,
        "runtime_seconds": time.perf_counter() - started,
    }
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote {output}")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--games-per-seat", type=int, default=10)
    parser.add_argument("--seed-start", type=int, default=70000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run_benchmark(args.games_per_seat, args.seed_start, args.output)
