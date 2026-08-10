# V34 Industrial Scale

V34 is a clean break from the conservative V19/V32 hill-climb.

## Objective
Maximize terminal productive capital and reward by converting the full farm into an industrial economy, rather than preserving cash or optimizing a single quadrant.

## Four-district operating model
- Q1 NW: early cash engine and intensive crops.
- Q2 NE: second crop-production district; unlock as soon as remaining-horizon payback is positive.
- Q3 SW: livestock/feed industrial district with dedicated capacity.
- Q4 SE: late-scale highest-return production district.

## Controller principles
1. Capital allocator chooses among land, worker, crop, animal and reserve using remaining-horizon marginal return.
2. Cash is not an objective. Idle cash above operating reserve is a deployment failure.
3. Land purchase is justified by expected remaining-horizon profit, not a fixed cash threshold.
4. Labour is productive capacity: hire when expected incremental production exceeds remaining wage cost.
5. Newly unlocked land must receive an activation plan immediately; purchased-but-idle land is a failure.
6. District specialization prevents crop and livestock work from cannibalizing each other.
7. Scale aggressively early; raise required payback as the horizon shrinks.
8. Endgame liquidates/reduces reinvestment when remaining payback becomes negative.

## Telemetry / promotion metrics
Track per game and per day:
- terminal reward and net worth
- quadrant unlock day for Q2/Q3/Q4
- productive and idle owned tiles by quadrant
- revenue/profit proxy by quadrant
- hands and idle-hand proxy
- cows/sheep and feed safety
- crop counts including strawberries
- cash and idle deployable cash
- land/worker/animal/crop market-action counts
- reinvestment rate

## Industrial gate
Do not promote based merely on beating V19.2. A candidate must demonstrate structural scale:
- zero invalid/error/timeouts
- both seats and multi-seed evaluation
- median terminal reward target >= 150000
- no catastrophic tail < 100000 for final-ready candidate
- Q3/Q4 materially activated in the majority of games
- productive utilization of acquired land, not merely land ownership

V19.2 remains a control for regression visibility, not the architecture parent or optimization ceiling.
