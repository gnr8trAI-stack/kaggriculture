"""Benchmark maturity-aware V7 against frozen V2."""
from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import asdict
from pathlib import Path
from typing import List

from agents.v2_frozen import agent as reference_agent
from agents.v7_lifecycle_core import agent as candidate_agent
from scripts.benchmark import GameResult, _run_game, summarize


def run_benchmark(games_per_seat: int, output: Path | None = None):
    if games_per_seat < 1:
        raise ValueError("games_per_seat must be at least 1")
    results: List[GameResult] = []
    for seat in (0, 1):
        for seed in range(games_per_seat):
            result = _run_game(seed, seat, candidate_agent, reference_agent)
            results.append(result)
            print(
                f"seed={seed:04d} seat={seat} v7={result.candidate_reward:.0f} "
                f"v2={result.opponent_reward:.0f} delta={result.delta:.0f} "
                f"status={result.candidate_status}"
            )
    summary = summarize(results)
    seat_mean_delta = {
        str(seat): statistics.fmean(r.delta for r in results if r.candidate_seat == seat)
        for seat in (0, 1)
    }
    payload = {
        "candidate": "agents.v7_lifecycle_core",
        "opponent": "agents.v2_frozen",
        "summary": asdict(summary),
        "seat_mean_delta": seat_mean_delta,
        "games": [asdict(result) for result in results],
    }
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    print(json.dumps({"seat_mean_delta": seat_mean_delta}, indent=2, sort_keys=True))
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote {output}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--games-per-seat", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run_benchmark(args.games_per_seat, args.output)
