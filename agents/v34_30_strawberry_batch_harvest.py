"""V34.30 isolated strawberry batch-harvest experiment.

Single mechanism on verified V34.26. Preserve its two-land dairy estate,
16-cow ceiling/window, six-hand dairy service, staffing, early strawberry
specialization, feed/routing/market behavior and explicit terminal liquidation.

Only change recurring STRAWBERRY service cadence: while a strawberry plant is
holding 1-2 units of yield, present it to the inherited scheduler as not yet
harvestable. At 3+ units it becomes visible normally. The environment state is
never mutated; this wrapper deep-copies only the observation passed to V34.26.

Economic rationale: strawberries are recurring producers with a held-yield cap.
Harvesting every small yield forces repeated worker travel and harvest actions.
Batching collection should increase value per existing crop tile by reducing
service frequency without buying land, labour, livestock or feed. Terminal
liquidation remains V34.26's responsibility.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from agents import v34_26_terminal_liquidation as _base

MIN_BATCH = 3
_DEFERRED = 0


def reset_state() -> None:
    global _DEFERRED
    _DEFERRED = 0
    _base.reset_state()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def terminal_liquidation_triggered() -> bool:
    return bool(_base.terminal_liquidation_triggered())


def deferred_strawberry_yields() -> int:
    return int(_DEFERRED)


def _is_strawberry(tile: Mapping[str, Any]) -> bool:
    for key in ("crop", "plant", "name", "resource", "crop_type", "plant_type"):
        value = tile.get(key)
        if value is not None and str(value).upper() == "STRAWBERRY":
            return True
    return False


def _batched_observation(observation: Any):
    global _DEFERRED
    if not isinstance(observation, dict):
        return observation
    farms = observation.get("farms")
    if not isinstance(farms, list):
        return observation

    patched = None
    for fi, farm in enumerate(farms):
        if not isinstance(farm, Mapping):
            continue
        tiles = farm.get("tiles")
        if not isinstance(tiles, list):
            continue
        for y, row in enumerate(tiles):
            if not isinstance(row, list):
                continue
            for x, tile in enumerate(row):
                if not isinstance(tile, Mapping) or not _is_strawberry(tile):
                    continue
                held = int(tile.get("yield_units", 0) or 0)
                if 0 < held < MIN_BATCH:
                    if patched is None:
                        patched = deepcopy(observation)
                    patched["farms"][fi]["tiles"][y][x]["yield_units"] = 0
                    _DEFERRED += 1
    return patched if patched is not None else observation


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    return _base.agent(_batched_observation(observation), configuration)
