"""Benchmark V14 against the strongest repository population."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents import v14_integrated_farm as candidate
from agents import v13_hybrid_champion, v12_agent, v11_agent
from agents.v10_market_front_runner import agent as v10_agent
from agents.melon_baseline import agent as baseline_agent
from agents.v7_lifecycle_core import agent as v7_agent
from scripts import benchmark_v11 as base


def run_benchmark(games_per_seat=10, seed_start=100000, output=None, telemetry_output=None):
    saved_candidate = base.v11_agent
    saved_opponents = base.OPPONENTS
    try:
        base.v11_agent = candidate
        base.OPPONENTS = {
            "v13_hybrid_champion": v13_hybrid_champion.agent,
            "v10_market_front_runner": v10_agent,
            "melon_baseline": baseline_agent,
            "v12_market_aware": v12_agent.agent,
            "v11_adaptive": v11_agent.agent,
            "v7_lifecycle_core": v7_agent,
        }
        payload = base.run_benchmark(games_per_seat, seed_start, output, telemetry_output)
        payload["candidate"] = "agents.v14_integrated_farm"
        if output is not None:
            import json
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload
    finally:
        base.v11_agent = saved_candidate
        base.OPPONENTS = saved_opponents


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--games-per-seat", type=int, default=10)
    parser.add_argument("--seed-start", type=int, default=100000)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--telemetry-output", type=Path)
    args = parser.parse_args()
    run_benchmark(args.games_per_seat, args.seed_start, args.output, args.telemetry_output)
