"""Submission-safe entry point for the V11 adaptive planner."""
from typing import Any, Dict

from agents.v11_adaptive_planner import agent as _planner_agent

LAST_DECISION: Dict[str, Any] = {}


def agent(observation: Any, configuration: Any = None) -> Dict[str, Any]:
    """Return only fields accepted by the Kaggriculture action schema."""
    global LAST_DECISION
    action = dict(_planner_agent(observation, configuration))
    telemetry = action.pop("_telemetry", None)
    LAST_DECISION = telemetry if isinstance(telemetry, dict) else {}
    return {
        "farmer": action.get("farmer", ["PASS"]),
        "hands": action.get("hands", []),
        "market": action.get("market", []),
    }
