"""Submission-safe entry point for the V12 market-aware agent."""
from typing import Any, Dict

# Import applies the market-aware choose_crop override to the V11 planner.
from agents import v12_market_aware as _policy  # noqa: F401
from agents import v11_agent as _telemetry_wrapper

TELEMETRY_SCHEMA_VERSION = _telemetry_wrapper.TELEMETRY_SCHEMA_VERSION


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    return _telemetry_wrapper.agent(observation, configuration)


def reset_telemetry() -> None:
    _telemetry_wrapper.reset_telemetry()


def get_telemetry(clear: bool = False):
    return _telemetry_wrapper.get_telemetry(clear=clear)
