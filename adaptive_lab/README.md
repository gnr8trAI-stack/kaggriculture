# Adaptive Replay Lab

This branch turns Kaggriculture agent development into a repeatable replay-trained workflow.

## Pipeline

1. Harvest public Kaggle replays and logs.
2. Deduplicate episodes and split chronologically.
3. Extract public state/action trajectories only.
4. Classify strategy families and rank strong routes.
5. Build a compact route library and conditional-memory medoids.
6. Generate an adaptive route-selector agent with safe repair and planner fallback.
7. Benchmark across both seats, many seeds/town realizations and a repository population.
8. Promote only on Bradley-Terry strength, zero invalid games and acceptable seat balance.
9. Emit a standalone `dist/main.py` for Kaggle submission.

## Important evaluation rule

Do not assume a fixed configured seed guarantees an identical town trajectory after planner changes. Occupancy-changing actions alter weed RNG consumption and can therefore change later town draws in some engine versions. Planner-changing experiments must be evaluated distributionally across many episodes.

## Runtime design

The submitted agent should use four layers:

- route selection from public opening state;
- exact replay while the live state stays close to the stored trajectory;
- bounded safe repairs for WATER/FEED/DIG/DROP and sell-order reordering;
- deterministic planner fallback when route divergence becomes material.

Replay memory must never depend on opponent-private state.
