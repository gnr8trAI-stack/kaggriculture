# V33 Industrial

V33 is a clean strategic break from the V19/V32 hill-climb. Its objective is terminal productive capital and reward, not conservative farm survival.

## Economic objective
Maximize terminal reward by maximizing the compounding productive base subject to zero-invalid execution and feed/operating solvency.

## Four-district plan
- Q1/NW: bootstrap cash engine; fast-turn crop production and initial labour.
- Q2/NE: second crop-production district; acquired as soon as remaining-horizon payback is positive.
- Q3/SW: industrial livestock/feed district; dedicated pasture/feed capacity, cows/sheep and livestock labour.
- Q4/SE: late-scale highest marginal-return district; crop/livestock allocation selected from observed realized ROI.

Land is productive capital, not a luxury. Expansion is evaluated by remaining-horizon payback, including land + setup + labour cost and expected production cycles. Idle affordable productive land is penalized.

## Capital allocator
Every discretionary coin competes among: land, worker, productive tile/crop, cow, sheep, feed capacity, and cash reserve. Rank investments by estimated remaining-game marginal return. Reserve cash only for mandatory feed/replant/near-term operating obligations plus a small execution buffer.

## Labour
Workers are productive capacity. Track useful actions per worker and district. Hire when expected additional district throughput repays labour before game end. Avoid cross-district labour starvation.

## Required telemetry
Per step/day and per quadrant where observable:
- cash and estimated net worth
- owned/unlocked land count and unlock step
- productive vs idle owned tiles
- crop inventory/plantings/harvests/sales
- cows, sheep, feed state and livestock sales/output
- hands/workers and useful/idle actions
- market actions and spend/revenue by category
- cumulative land/labour/livestock/crop capex
- realized revenue/profit proxy by district
- reinvestment ratio

## Benchmark gates
Do not promote merely for beating V19.2. Primary frontier is absolute industrial output.

Stage A, mechanics: zero invalid/error/timeout; demonstrate operation in Q3/Q4 and meaningful multi-land utilization.
Stage B, economics: multi-seed both-seat distribution with improving day-12/day-20/day-25 capital trajectory and terminal reward.
Stage C, target: >=24 games, median terminal reward >=150000, minimum >=100000, zero invalids. Only then label 150K-ready.

V19.2 remains a reference control, not the architecture parent.
