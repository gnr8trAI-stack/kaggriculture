"""Population benchmark for a generated adaptive submission."""
from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.benchmark import _run_game


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, "agent", None)
    if not callable(fn):
        raise TypeError(f"{path} does not expose agent")
    return fn


def _fit_bt(games, iterations=600, lr=0.03):
    agents = sorted({x for a, b, _ in games for x in (a, b)})
    rating = {a: 0.0 for a in agents}
    for _ in range(iterations):
        grad = {a: 0.0 for a in agents}
        count = Counter()
        for a, b, sa in games:
            d = max(-20.0, min(20.0, rating[a] - rating[b]))
            p = 1.0 / (1.0 + math.exp(-d))
            e = sa - p
            grad[a] += e
            grad[b] -= e
            count[a] += 1
            count[b] += 1
        for agent in agents:
            rating[agent] += lr * grad[agent] / max(1, count[agent])
        mean = statistics.fmean(rating.values()) if rating else 0.0
        for agent in agents:
            rating[agent] -= mean
    return rating


def run(candidate_path: Path, opponents: list[tuple[str, Path]], games_per_seat: int, seed_start: int, output: Path) -> None:
    candidate = _load(candidate_path, "adaptive_candidate")
    rows = []
    bt_games = []
    for opponent_name, opponent_path in opponents:
        opponent = _load(opponent_path, f"opponent_{opponent_name}")
        for seat in (0, 1):
            for offset in range(games_per_seat):
                seed = seed_start + offset
                started = time.perf_counter()
                result = _run_game(seed, seat, candidate, opponent)
                runtime = time.perf_counter() - started
                outcome = "win" if result.delta > 0 else "loss" if result.delta < 0 else "tie"
                score = 1.0 if outcome == "win" else 0.0 if outcome == "loss" else 0.5
                bt_games.append(("candidate", opponent_name, score))
                rows.append({
                    "candidate": "candidate",
                    "opponent": opponent_name,
                    "result": outcome,
                    "seat": seat,
                    "seed": seed,
                    "candidate_reward": result.candidate_reward,
                    "opponent_reward": result.opponent_reward,
                    "delta": result.delta,
                    "candidate_status": result.candidate_status,
                    "opponent_status": result.opponent_status,
                    "runtime_seconds": runtime,
                })
                print(rows[-1])

    ratings = _fit_bt(bt_games)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = defaultdict(list)
    for row in rows:
        summary[row["opponent"]].append(row)
    print("\nBradley-Terry ratings:", ratings)
    for opponent, values in summary.items():
        wins = sum(v["result"] == "win" for v in values)
        losses = sum(v["result"] == "loss" for v in values)
        ties = sum(v["result"] == "tie" for v in values)
        invalid = sum(v["candidate_status"] in {"ERROR", "INVALID", "TIMEOUT"} for v in values)
        seat_delta = {
            seat: statistics.fmean(v["delta"] for v in values if v["seat"] == seat)
            for seat in (0, 1)
        }
        print(opponent, {"games": len(values), "wins": wins, "losses": losses, "ties": ties, "invalid": invalid, "mean_delta": statistics.fmean(v["delta"] for v in values), "seat_mean_delta": seat_delta})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, default=Path("dist/main.py"))
    parser.add_argument("--opponent", action="append", default=[], help="name=path.py; repeatable")
    parser.add_argument("--games-per-seat", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=600000)
    parser.add_argument("--output", type=Path, default=Path("artifacts/adaptive_population_results.csv"))
    args = parser.parse_args()
    opponents = []
    for item in args.opponent:
        name, raw_path = item.split("=", 1)
        opponents.append((name, Path(raw_path)))
    if not opponents:
        opponents = [
            ("v2_frozen", Path("agents/v2_frozen.py")),
            ("v10_market_front_runner", Path("agents/v10_market_front_runner.py")),
            ("v11_adaptive", Path("agents/v11_agent.py")),
        ]
    run(args.candidate, opponents, args.games_per_seat, args.seed_start, args.output)
