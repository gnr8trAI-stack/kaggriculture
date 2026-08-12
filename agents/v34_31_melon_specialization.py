"""V34.31 isolated mature-estate MELON specialization.

Single mechanism on verified V34.26. Preserve its two-land dairy estate,
16-cow ceiling/window, six-hand livestock service, late staffing, feed/routing,
activation rescue and explicit terminal liquidation. Change only the mature
crop choice used by the already-proven V34.23 specialization gate: choose MELON
instead of STRAWBERRY for newly planted eligible crop slots.

Economic rationale: V34.30 proved strawberry harvest batching is behaviorally
irrelevant, so crop service frequency is not the bottleneck. MELON is a
one-shot premium crop with materially higher gross value per occupied tile and
requires no recurring harvest loop. This test asks whether value per existing
two-land crop slot, rather than more acreage/labour, is the next profit lever.
"""
from __future__ import annotations
from typing import Any

from agents import v34_26_terminal_liquidation as _base

# V34.26 -> V34.23 -> V34.21. V34.21 owns the dynamic choose_crop hook.
_crop_layer = _base._base._base
_ORIGINAL_SPECIALIZED = _crop_layer._choose_crop
_TRIGGERED = False


def _melon_choose_crop(obs, farm):
    global _TRIGGERED
    observation = _crop_layer._CURRENT_OBS if _crop_layer._CURRENT_OBS is not None else obs
    if _crop_layer._eligible(observation):
        _TRIGGERED = True
        return "MELON", {"MELON": 1.0}
    original = _crop_layer._ORIGINAL_CHOOSE_CROP
    if callable(original):
        return original(obs, farm)
    return None, {}


def _activate() -> None:
    _crop_layer._choose_crop = _melon_choose_crop
    _crop_layer._activate()


def reset_state() -> None:
    global _TRIGGERED
    _TRIGGERED = False
    _base.reset_state()
    _activate()


def reset_telemetry() -> None:
    reset_state()


def get_telemetry(clear: bool = False):
    return _base.get_telemetry(clear=clear)


def melon_triggered() -> bool:
    return bool(_TRIGGERED)


def terminal_liquidation_triggered() -> bool:
    return bool(_base.terminal_liquidation_triggered())


def agent(observation: Any, configuration: Any = None):
    _activate()
    return _base.agent(observation, configuration)


_activate()
