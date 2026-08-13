# Kaggriculture Live Evaluation Protocol

## Purpose

Internal simulation is an engineering diagnostic, not a final promotion authority.
Every mechanically valid candidate must be preserved and packaged so it can be
pitched into the real Kaggle field. Promotion decisions should use real replay
results whenever a live submission exists.

## Candidate lifecycle

1. Build a candidate from a clearly stated hypothesis.
2. Compile and run a minimal smoke test to catch invalid agents/timeouts.
3. Always create a root-only `main.py` submission ZIP for mechanically valid builds.
4. Record internal simulator results as diagnostics; do not delete/reject the build.
5. Submit the candidate to the Kaggle live arena/leaderboard.
6. Collect real episodes for that exact submission ID from the public replay corpus.
7. Evaluate live results across opponents, seats, towns and time windows.
8. Promote, retain as specialist, or retire only after live evidence is available.

## Live decision metrics

Primary:
- Bradley-Terry / pairwise win strength across real opponents
- real reward distribution: p10 / median / p90 / max
- win rate and seat asymmetry
- percentage of trials over 50k / 100k / 150k / 175k / 200k

Secondary diagnostics:
- terminal inventory / liquidation
- land timing and district count
- livestock mix and active service rate
- crop mix
- hand count / labor saturation
- weed failures and invalid actions

## Candidate labels

- `READY_FOR_LIVE`: mechanically valid and packaged. Internal score does not veto live testing.
- `LIVE_TESTING`: submission is active and replay sample is accumulating.
- `LIVE_PROMOTED`: strongest broad real-world result so far.
- `LIVE_SPECIALIST`: useful against a subset of opponents/towns/seats.
- `LIVE_RETIRED`: enough real-world evidence shows it is dominated.
- `BROKEN`: compile/contract/timeout/invalid submission failure only.

## Current queue

| Candidate | Internal status | Live status | Action |
|---|---|---|---|
| V15 champion | proven historical baseline | live-tested historically | retain control |
| V19 livestock compound | ~50k local control range | live test/retest | highest-priority control |
| V21 alpha1 | poor reported live behavior | live evidence exists | retain as negative control |
| V21 alpha2 | ~V19 internally | not final-promoted | package/field if slot permits |
| V22.1/V22.2 | structural experiments | not enough live evidence | preserve; lower live priority |
| V23 alpha2 donor clock | very poor internal transfer but mechanically valid | not live-tested | package; field as experimental probe if submission capacity permits |

## Development cadence

Each engineering stage must produce something usable: a packaged candidate, a
live result, a replay analysis, or a concrete policy extraction artifact. No
open-ended version chain is allowed without live feedback.
