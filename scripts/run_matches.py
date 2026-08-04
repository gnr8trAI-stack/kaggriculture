"""Run deterministic local matches using the installed Kaggle environment."""
from __future__ import annotations

import argparse
from kaggle_environments import make

from agents.adaptive_agent import agent


def passive_agent(observation, configuration=None):
    farm = observation["farms"][observation["player"]]
    return {"farmer": ["PASS"], "hands": [["PASS"] for _ in farm.get("hands", [])], "market": []}


def main(games: int) -> None:
    wins = ties = losses = 0
    for seed in range(games):
        env = make("kaggriculture", configuration={"seed": seed}, debug=True)
        env.run([agent, passive_agent])
        left, right = env.state[0].reward, env.state[1].reward
        wins += left > right
        ties += left == right
        losses += left < right
        print(f"seed={seed:03d} agent={left} passive={right}")
    print({"wins": wins, "ties": ties, "losses": losses})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=20)
    args = parser.parse_args()
    main(args.games)
