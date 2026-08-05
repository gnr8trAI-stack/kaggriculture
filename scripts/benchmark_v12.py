"""Benchmark V12 with the V11 telemetry and opponent population."""
import argparse
from pathlib import Path

from agents import v12_agent
from scripts import benchmark_v11 as base


def run_benchmark(
    games_per_seat: int,
    seed_start: int = 80000,
    output: Path = None,
    telemetry_output: Path = None,
):
    original = base.v11_agent
    try:
        base.v11_agent = v12_agent
        payload = base.run_benchmark(
            games_per_seat,
            seed_start,
            output,
            telemetry_output,
        )
        payload["candidate"] = "agents.v12_agent"
        if output is not None:
            import json
            output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload
    finally:
        base.v11_agent = original


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--games-per-seat", type=int, default=10)
    parser.add_argument("--seed-start", type=int, default=80000)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--telemetry-output", type=Path)
    args = parser.parse_args()
    run_benchmark(
        args.games_per_seat,
        args.seed_start,
        args.output,
        args.telemetry_output,
    )
