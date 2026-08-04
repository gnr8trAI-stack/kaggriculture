# Architecture

## Goal

Maximize terminal cash over the Kaggriculture season while remaining comfortably within the one-second action timeout.

## Initial policy

The first agent is intentionally conservative:

1. Parse mapping and Struct-like observations safely.
2. Service the object under the farmer before expanding.
3. Harvest before watering, feeding or caring.
4. Maintain a small low-risk wheat seed buffer.
5. Sell accumulated stock and force liquidation near season end.
6. Return `PASS` rather than emit an uncertain action.

## Why no LLM in the turn loop

The environment is structured, latency-constrained and deterministic. Network calls or language-model inference would add latency and nondeterminism without solving the core planning problem. LLMs may be used offline for replay analysis, hypothesis generation and experiment documentation.

## Known limitations

- No path planning yet.
- Hired hands currently pass.
- No reservation system for multi-unit tasks.
- No market-price forecasting.
- No opponent supply model.
- No fertilizer, animal acquisition or land expansion policy.
- The local runner must still be validated against the currently installed Kaggle runtime.

## Planned progression

1. Exact observation fixtures from real replays.
2. Movement and nearest-task planning.
3. Multi-worker task reservations.
4. Exact market/town forward model.
5. Crop, animal and expansion return calculations.
6. Seeded round-robin tournament and regression gates.
7. Search-based and learned policies with heuristic safety fallbacks.
