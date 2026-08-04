"""Benchmark Kaggriculture agents across seeds and both player positions.

The harness deliberately reports raw evidence instead of declaring a strategy
better from one or two games. It can write a machine-readable JSON report for
versioned experiments.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence, Tuple

from kaggle_environments import make

from agents.adaptive_agent import agent as candidate_agent

Agent = Callable[[Any, Any], Dict[str, Any]]


def passive_agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    """Schema-safe no-op opponent used only as a minimum sanity baseline."""
    farm = observation["farms"][observation["player"]]
    return {
        "farmer": ["PASS"],
        "hands": [["PASS"] for _ in farm.get("hands", [])],
        "market": [],
    }


@dataclass(frozen=True)
class GameResult:
    seed: int
    candidate_seat: int
    candidate_reward: float
    opponent_reward: float
    delta: float
    candidate_status: str
    opponent_status: str
    elapsed_seconds: float


@dataclass(frozen=True)
class BenchmarkSummary:
    games: int
    wins: int
    ties: int
    losses: int
    win_rate: float
    mean_candidate_reward: float
    mean_opponent_reward: float
    mean_delta: float
    median_delta: float
    min_delta: float
    max_delta: float
    invalid_or_error_games: int
    mean_game_seconds: float


def _run_game(seed: int, candidate_seat: int, candidate: Agent, opponent: Agent) -> GameResult:
    agents: Sequence[Agent] = [candidate, opponent] if candidate_seat == 0 else [opponent, candidate]
    env = make("kaggriculture", configuration={"seed": seed}, debug=True)
    started = time.perf_counter()
    env.run(list(agents))
    elapsed = time.perf_counter() - started

    candidate_state = env.state[candidate_seat]
    opponent_state = env.state[1 - candidate_seat]
    candidate_reward = float(candidate_state.reward or 0)
    opponent_reward = float(opponent_state.reward or 0)
    return GameResult(
        seed=seed,
        candidate_seat=candidate_seat,
        candidate_reward=candidate_reward,
        opponent_reward=opponent_reward,
        delta=candidate_reward - opponent_reward,
        candidate_status=str(candidate_state.status),
        opponent_status=str(opponent_state.status),
        elapsed_seconds=elapsed,
    )


def summarize(results: Sequence[GameResult]) -> BenchmarkSummary:
    if not results:
        raise ValueError("At least one game result is required")
    deltas = [result.delta for result in results]
    bad_statuses = {"ERROR", "INVALID", "TIMEOUT"}
    invalid = sum(
        result.candidate_status in bad_statuses or result.opponent_status in bad_statuses
        for result in results
    )
    wins = sum(delta > 0 for delta in deltas)
    ties = sum(delta == 0 for delta in deltas)
    losses = sum(delta < 0 for delta in deltas)
    return BenchmarkSummary(
        games=len(results),
        wins=wins,
        ties=ties,
        losses=losses,
        win_rate=wins / len(results),
        mean_candidate_reward=statistics.fmean(r.candidate_reward for r in results),
        mean_opponent_reward=statistics.fmean(r.opponent_reward for r in results),
        mean_delta=statistics.fmean(deltas),
        median_delta=statistics.median(deltas),
        min_delta=min(deltas),
        max_delta=max(deltas),
        invalid_or_error_games=invalid,
        mean_game_seconds=statistics.fmean(r.elapsed_seconds for r in results),
    )


def run_benchmark(games_per_seat: int, output: Path | None = None) -> BenchmarkSummary:
    if games_per_seat < 1:
        raise ValueError("games_per_seat must be at least 1")

    results: List[GameResult] = []
    for seat in (0, 1):
        for seed in range(games_per_seat):
            result = _run_game(seed, seat, candidate_agent, passive_agent)
            results.append(result)
            print(
                f"seed={seed:04d} seat={seat} candidate={result.candidate_reward:.0f} "
                f"opponent={result.opponent_reward:.0f} delta={result.delta:.0f} "
                f"status={result.candidate_status}"
            )

    summary = summarize(results)
    payload = {
        "summary": asdict(summary),
        "games": [asdict(result) for result in results],
    }
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))

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
