"""Build the standalone V12 market-aware Kaggriculture submission."""
from pathlib import Path


def _overlay_source(text: str) -> str:
    start = text.index("MARKET_PARAMS =")
    end = text.index("# V11's agent resolves choose_crop")
    body = text[start:end]
    replacements = {
        "planner.CROPS": "CROPS",
        "planner._mapping": "_mapping",
        "planner._crop_counts": "_crop_counts",
        "planner._remaining_days": "_remaining_days",
        "planner.ENDGAME_BUFFER_DAYS": "ENDGAME_BUFFER_DAYS",
    }
    for old, new in replacements.items():
        body = body.replace(old, new)
    return body


def build() -> Path:
    root = Path(__file__).resolve().parents[1]
    planner = (root / "agents" / "v11_adaptive_planner.py").read_text(encoding="utf-8")
    overlay = (root / "agents" / "v12_market_aware.py").read_text(encoding="utf-8")
    output = root / "dist" / "submission.py"
    output.parent.mkdir(parents=True, exist_ok=True)
    text = (
        '"""Standalone Kaggriculture V12 market-aware submission."""\n\n'
        + planner
        + "\n\n# V12 market-aware crop-selection override.\n"
        + "import math\n\n"
        + _overlay_source(overlay)
    )
    output.write_text(text, encoding="utf-8")
    return output


if __name__ == "__main__":
    path = build()
    print(path)
    print(path.stat().st_size)
