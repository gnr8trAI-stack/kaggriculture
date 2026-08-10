# V31 Elite-Trajectory Economic Learner

Status: research / no Kaggle submission yet.

## Objective

Break out of the ~40–50k terminal-cash regime by learning the *economic transitions* used by the strongest public replay trajectories instead of copying their final farm shapes or replay routes.

V19 remains a safety/control baseline only. V30.0 is rejected (0-10 vs the available V19 proxy, mean terminal cash 23.6k vs 34.6k).

## V31 hypothesis

The important signal is not that an elite player eventually owns N hands, M land quadrants or K animals. The signal is the sequence:

`state -> capital allocation / production / sale action -> next state -> terminal wealth`

For every elite replay V31 will extract:

- day/hour and current money;
- opponent money and relative wealth;
- land quadrants and productive occupancy;
- worker count and hires-today;
- crop, pasture, coop, weed and animal counts;
- public market price/inventory state;
- farmer/hand/market actions;
- next-turn money delta;
- terminal reward and terminal wealth uplift from the current state.

## Elite cohort

Initial cohort is selected from winning trajectories by terminal-reward quantile. We will compare several cutoffs (top 20%, 10%, 5%, 1%) rather than assume one threshold. Later weighting will incorporate opponent strength / Bradley-Terry evidence when identity data is available.

## Outputs

`v31_extract_elite_transitions.py` generates lightweight artifacts:

- `elite_transitions.csv` — state/action/next-money training rows;
- `elite_checkpoints.csv` — wealth/capacity percentiles at key days;
- `elite_action_value.csv` — action-signature statistics by phase;
- `elite_summary.json` — corpus and elite-cohort diagnostics.

Large replay JSON remains external / workflow artifact data and is never committed.

## Promotion philosophy

Do not promote a V31 agent because it beats V19 by a few percent. A candidate must show a qualitatively different wealth curve. The first economic gate is median terminal cash >= 100k in a credible holdout population, followed by 200k+ frontier work. Kaggle submission happens only after compile/runtime validation and evidence that the new policy is not another sub-50k local optimum.
