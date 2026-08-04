# Kaggriculture AI Agent Lab

Research and engineering workspace for the Kaggle **Kaggriculture** competition.

## Current status

This repository contains the first testable foundation:

- schema-safe adaptive heuristic agent
- deterministic local match runner
- standalone submission builder
- contract tests
- architecture, strategy, rules and testing documentation
- CI validation

The current policy is an **experimental baseline**, not yet a leaderboard-validated final agent. Strategy changes must be promoted only after deterministic seeded evaluation.

## Environment constraints

- Two competing agents
- 720 default turns: 24 turns/day for 30 days
- One-second action timeout
- Up to ten market orders per turn
- Final reward is terminal cash
- Public farm/market/town state; private shed/inventory/seed state
- Dynamic prices driven by market inventory and town demand

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest
```

## Run local matches

```bash
python scripts/run_matches.py --games 20
```

## Build submission

```bash
python scripts/build_submission.py
```

The generated standalone file is written to `dist/submission.py`.

## Principles

1. No network or LLM calls inside the turn loop.
2. Standard-library-only final submission unless Kaggle availability is verified.
3. Service existing assets before expansion.
4. Treat unsold terminal inventory as a failure.
5. Require seeded benchmark evidence for policy changes.
6. Recheck live competition rules before final submission.
