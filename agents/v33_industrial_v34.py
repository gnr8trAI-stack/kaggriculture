"""V33.34 burst-clearing + eight-hand livestock service experiment.

Single mechanism over V33.32: increase only the maximum dedicated livestock
service crew from seven to eight hands once Q3 is unlocked.  V33.32's market
policy, crop allocator, land gates, cow target, feed reserve, capex logic and
D27 liquidation are unchanged.

Economic rationale: V33.32 is the strongest current independent industrial
lineage (24 games, median 71,439.5, zero invalid) but reaches only median 6.5
animals despite median 15 hands and 8 Q3 pastures.  The older isolated V34.4
experiment showed that moving livestock service from six to eight hands was
sufficient to activate the full 12-cow herd in 24/32 games.  This test asks
whether one extra service hand converts V33.32's already-built Q3 pasture and
labor capacity into more productive cows without changing any other economics.
"""
from __future__ import annotations
from typing import Any, List
from agents import v33_industrial_v32 as _v32

_v28 = _v32._v28
_b = _v32._b


def _roles_crew8(lands: int, hand_count: int) -> List[str]:
    total = hand_count + 1
    roles = ["q1"] * total
    if lands >= 2:
        for i in range(1, total):
            roles[i] = "q2" if i % 2 else "q1"
    if lands >= 3:
        # V33.32/V33.28 used min(7, max(4,total//3)).  Change only this ceiling.
        crew = min(8, max(4, total // 3))
        for i in range(max(1, total - crew), total):
            roles[i] = "livestock"
        fi = total - crew - 1
        if fi >= 1:
            roles[fi] = "feed"
    if lands >= 4:
        moved = 0
        for i in range(1, total):
            if roles[i] in {"q1", "q2"} and moved < 3:
                roles[i] = "q4"
                moved += 1
    return roles


# Install only the role-allocation delta.  All V33.32 market/economic functions
# remain installed by importing v33_industrial_v32 above.
_v28._roles = _roles_crew8
_b._roles = _roles_crew8


def agent(observation: Any, configuration: Any = None):
    return _v28.agent(observation, configuration)


def reset_state():
    return _v28.reset_state()


def reset_telemetry():
    return reset_state()


def get_telemetry(clear: bool = False):
    return _v28.get_telemetry(clear=clear)
