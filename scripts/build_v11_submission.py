"""Build a standalone Kaggriculture V11 submission.

The generated file includes the adaptive planner and a minimal schema-sanitising
wrapper. Local telemetry history is intentionally excluded from the submitted
artifact; the planner's latest decision snapshot remains available as
``LAST_DECISION`` without being returned to Kaggle.
"""
from pathlib import Path


WRAPPER = r'''

LAST_DECISION = {}


def agent(observation, configuration=None):
    """Return only fields accepted by the Kaggriculture action schema."""
    global LAST_DECISION
    raw = dict(_planner_agent(observation, configuration))
    telemetry = raw.pop("_telemetry", None)
    LAST_DECISION = telemetry if isinstance(telemetry, dict) else {}
    return {
        "farmer": raw.get("farmer", ["PASS"]),
        "hands": raw.get("hands", []),
        "market": raw.get("market", []),
    }
'''


def build() -> Path:
    root = Path(__file__).resolve().parents[1]
    source = root / "agents" / "v11_adaptive_planner.py"
    output = root / "dist" / "submission.py"
    output.parent.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8")
    marker = "def agent(observation: Any, configuration: Any = None)"
    if marker not in text:
        raise RuntimeError("Could not locate V11 planner entry point")
    text = text.replace(marker, "def _planner_agent(observation: Any, configuration: Any = None)", 1)
    output.write_text(
        '"""Standalone Kaggriculture V11 competition submission."""\n\n'
        + text
        + WRAPPER,
        encoding="utf-8",
    )
    return output


if __name__ == "__main__":
    path = build()
    print(path)
    print(path.stat().st_size)
