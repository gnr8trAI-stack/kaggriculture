# V30 Economic Compounder

Status: alpha / research only / not submitted to Kaggle.

Objective: break the V19 ~40–50k terminal-cash regime by treating land, labour, livestock and sales as capital-allocation decisions rather than replay-shaped fixed schedules.

Current alpha1 implementation is preserved in the ChatGPT Library at `/kaggriculture/v30/kaggriculture_v30_economic_compounder.py` while the branch is used as the research control plane.

## Alpha1 design

- Base operating machinery: V21 Scarcity Harvester routing/crop/livestock service loop.
- Land: sequential NE/SW/SE unlocks gated by occupancy, farm health, remaining season and post-purchase liquidity.
- Cows: staged herd growth; live milk/wheat economics are used as an NPV gate before purchases; animals are bought only for built empty pastures.
- Labour: workload-derived target with marginal Fibonacci hire-cost gate; hard ceiling 9 hands in alpha1.
- Sales: product-specific scarcity thresholds. Milk waits for scarcity/demand, melon sells earlier because its glut curve is highly convex, staples fund working capital, and days 28–29 force liquidation.
- Investment cutoff: no new long-payback scale after day 20.

## Economic gates to instrument

- cash at days 5, 8, 12, 15, 20, 25 and terminal
- land unlock days
- productive occupancy by district
- active cows / pasture count
- worker count and daily hire spend
- milk/melon realized sell price vs live market price
- inventory discarded/unsold at terminal
- action utilization and livestock service misses

## Promotion rule

V30 must first clear internal wealth gates and then beat the exact V19.2 early-scale8 champion in paired both-seat tests. It must not be submitted merely to discover whether the architecture works.
