"""Benchmark V11 and export per-turn decision telemetry as JSON Lines."""
import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.melon_baseline import agent as melon_baseline
from agents.v7_lifecycle_core import agent as v7_agent
from agents.v10_market_front_runner import agent as v10_agent
from agents import v11_agent
from scripts.benchmark import _run_game, summarize

OPPONENTS = {
    "v10_market_front_runner": v10_agent,
    "melon_baseline": melon_baseline,
    "v7_lifecycle_core": v7_agent,
}


def _telemetry_summary(records):
    if not records:
        return {
            "records": 0,
            "mean_decision_ms": 0.0,
            "max_decision_ms": 0.0,
            "selected_crop_counts": {},
            "action_counts": {},
        }
    durations = [float(record.get("decision_duration_ms", 0) or 0) for record in records]
    crop_counts = {}
    action_counts = {}
    for record in records:
        crop = record.get("planner", {}).get("selected_crop")
        key = str(crop or "NONE")
        crop_counts[key] = crop_counts.get(key, 0) + 1
        for action, count in record.get("action", {}).get("counts", {}).items():
            action_counts[action] = action_counts.get(action, 0) + int(count or 0)
    return {
        "records": len(records),
        "mean_decision_ms": statistics.fmean(durations),
        "median_decision_ms": statistics.median(durations),
        "max_decision_ms": max(durations),
        "p95_decision_ms": sorted(durations)[min(len(durations) - 1, int(len(durations) * 0.95))],
        "selected_crop_counts": crop_counts,
        "action_counts": action_counts,
    }


def run_benchmark(
    games_per_seat: int,
    seed_start: int = 70000,
    output: Path = None,
    telemetry_output: Path = None,
):
    if games_per_seat < 1:
        raise ValueError("games_per_seat must be at least 1")
    started = time.perf_counter()
    all_results = []
    all_telemetry = []
    by_opponent = {}

    telemetry_handle = None
    if telemetry_output is not None:
        telemetry_output.parent.mkdir(parents=True, exist_ok=True)
        telemetry_handle = telemetry_output.open("w", encoding="utf-8")

    try:
        for opponent_name, opponent_agent in OPPONENTS.items():
            results = []
            opponent_telemetry = []
            opponent_started = time.perf_counter()
            for seat in (0, 1):
                for offset in range(games_per_seat):
                    seed = seed_start + offset
                    v11_agent.reset_telemetry()
                    result = _run_game(seed, seat, v11_agent.agent, opponent_agent)
                    records = v11_agent.get_telemetry(clear=True)
                    for record in records:
                        enriched = {
                            "opponent": opponent_name,
                            "seed": seed,
                            "candidate_seat": seat,
                            **record,
                        }
                        opponent_telemetry.append(enriched)
                        all_telemetry.append(enriched)
                        if telemetry_handle is not None:
                            telemetry_handle.write(json.dumps(enriched, sort_keys=True) + "\n")
                    results.append(result)
                    all_results.append(result)
                    print(
                        f"opponent={opponent_name} seed={seed} seat={seat} "
                        f"v11={result.candidate_reward:.0f} opponent_reward={result.opponent_reward:.0f} "
                        f"delta={result.delta:+.0f} status={result.candidate_status} "
                        f"telemetry={len(records)}"
                    )
            summary = summarize(results)
            by_opponent[opponent_name] = {
                "summary": asdict(summary),
                "seat_mean_delta": {
                    str(seat): statistics.fmean(r.delta for r in results if r.candidate_seat == seat)
                    for seat in (0, 1)
                },
                "runtime_seconds": time.perf_counter() - opponent_started,
                "telemetry_summary": _telemetry_summary(opponent_telemetry),
                "games": [asdict(result) for result in results],
            }
    finally:
        if telemetry_handle is not None:
            telemetry_handle.close()

    overall = summarize(all_results)
    payload = {
        "candidate": "agents.v11_agent",
        "summary": asdict(overall),
        "seat_mean_delta": {
            str(seat): statistics.fmean(r.delta for r in all_results if r.candidate_seat == seat)
            for seat in (0, 1)
        },
        "telemetry_schema_version": v11_agent.TELEMETRY_SCHEMA_VERSION,
        "telemetry_summary": _telemetry_summary(all_telemetry),
        "telemetry_output": str(telemetry_output) if telemetry_output else None,
        "by_opponent": by_opponent,
        "runtime_seconds": time.perf_counter() - started,
    }
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    print(json.dumps(payload["telemetry_summary"], indent=2, sort_keys=True))
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote {output}")
    if telemetry_output is not None:
        print(f"wrote {telemetry_output}")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--games-per-seat", type=int, default=10)
    parser.add_argument("--seed-start", type=int, default=70000)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--telemetry-output", type=Path)
    args = parser.parse_args()
    run_benchmark(
        args.games_per_seat,
        args.seed_start,
        args.output,
        args.telemetry_output,
    )
