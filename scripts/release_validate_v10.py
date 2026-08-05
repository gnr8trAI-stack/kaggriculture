"""Release-grade validation for the exact standalone V10 submission."""
from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from kaggle_environments import make

from agents.melon_baseline import agent as melon_baseline
from agents.v2_frozen import agent as v2_agent
from agents.v7_lifecycle_core import agent as v7_agent
from agents.v8_melon_optimizer import agent as v8_agent
from scripts.benchmark import GameResult, summarize
from scripts.build_v10_submission import build


def load_submission(path: Path):
    spec = importlib.util.spec_from_file_location("release_submission", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    candidate = getattr(module, "agent", None)
    if not callable(candidate):
        raise RuntimeError("submission.py does not expose callable agent")
    return candidate


def official_starter():
    try:
        from kaggle_environments.envs.kaggriculture.kaggriculture import starter_agent
        if callable(starter_agent):
            return starter_agent
    except Exception:
        pass
    return "random"


def run_game(seed: int, seat: int, candidate: Any, opponent: Any) -> GameResult:
    agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
    env = make("kaggriculture", configuration={"seed": seed}, debug=True)
    started = time.perf_counter()
    env.run(agents)
    elapsed = time.perf_counter() - started
    cs = env.state[seat]
    os = env.state[1 - seat]
    cr = float(cs.reward or 0)
    orr = float(os.reward or 0)
    return GameResult(
        seed=seed,
        candidate_seat=seat,
        candidate_reward=cr,
        opponent_reward=orr,
        delta=cr - orr,
        candidate_status=str(cs.status),
        opponent_status=str(os.status),
        elapsed_seconds=elapsed,
    )


def run(games_per_seat: int, start_seed: int, output: Path) -> Dict[str, Any]:
    submission_path = build()
    candidate = load_submission(submission_path)
    opponents = {
        "melon_baseline": melon_baseline,
        "v8_melon_optimizer": v8_agent,
        "v7_lifecycle_core": v7_agent,
        "v2_frozen": v2_agent,
        "official_starter": official_starter(),
        "random": "random",
    }

    started = time.perf_counter()
    all_results: List[GameResult] = []
    by_opponent: Dict[str, Any] = {}

    for name, opponent in opponents.items():
        results: List[GameResult] = []
        opponent_started = time.perf_counter()
        for seat in (0, 1):
            for offset in range(games_per_seat):
                seed = start_seed + offset
                result = run_game(seed, seat, candidate, opponent)
                results.append(result)
                all_results.append(result)
                print(
                    f"opponent={name} seed={seed} seat={seat} "
                    f"candidate={result.candidate_reward:.0f} "
                    f"opponent_reward={result.opponent_reward:.0f} "
                    f"delta={result.delta:+.0f} status={result.candidate_status}"
                )
        summary = summarize(results)
        by_opponent[name] = {
            "summary": asdict(summary),
            "seat_mean_delta": {
                str(seat): statistics.fmean(r.delta for r in results if r.candidate_seat == seat)
                for seat in (0, 1)
            },
            "runtime_seconds": time.perf_counter() - opponent_started,
            "games": [asdict(r) for r in results],
        }

    overall = summarize(all_results)
    payload = {
        "candidate": "dist/submission.py",
        "start_seed": start_seed,
        "games_per_seat": games_per_seat,
        "summary": asdict(overall),
        "seat_mean_delta": {
            str(seat): statistics.fmean(r.delta for r in all_results if r.candidate_seat == seat)
            for seat in (0, 1)
        },
        "by_opponent": by_opponent,
        "runtime_seconds": time.perf_counter() - started,
        "submission_size_bytes": submission_path.stat().st_size,
    }

    serious = ["melon_baseline", "v8_melon_optimizer", "v7_lifecycle_core", "v2_frozen"]
    gates = {
        "zero_invalid_or_error_games": overall.invalid_or_error_games == 0,
        "positive_overall_delta": overall.mean_delta > 0,
        "positive_both_seats": all(value > 0 for value in payload["seat_mean_delta"].values()),
        "win_rate_at_least_90pct": overall.win_rate >= 0.90,
        "positive_against_serious_opponents": all(
            by_opponent[name]["summary"]["mean_delta"] > 0 for name in serious
        ),
        "positive_both_seats_against_melon": all(
            value > 0 for value in by_opponent["melon_baseline"]["seat_mean_delta"].values()
        ),
    }
    payload["release_gates"] = gates
    payload["release_ready"] = all(gates.values())

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    print(json.dumps(gates, indent=2, sort_keys=True))
    print(f"wrote {output}")

    if not payload["release_ready"]:
        raise SystemExit("V10 failed one or more release gates")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--games-per-seat", type=int, default=42)
    parser.add_argument("--start-seed", type=int, default=10000)
    parser.add_argument("--output", type=Path, default=Path("experiments/v10-release.json"))
    args = parser.parse_args()
    run(args.games_per_seat, args.start_seed, args.output)
