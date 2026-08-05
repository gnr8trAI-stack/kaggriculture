"""Build the exact standalone V10 Kaggriculture submission."""
from pathlib import Path


def build() -> Path:
    root = Path(__file__).resolve().parents[1]
    source = root / "agents" / "v10_market_front_runner.py"
    output = root / "dist" / "submission.py"
    output.parent.mkdir(parents=True, exist_ok=True)

    # Preserve the source module exactly so any ``from __future__`` import
    # remains in its required position immediately after the module docstring.
    text = source.read_text(encoding="utf-8")
    output.write_text(text, encoding="utf-8")
    return output


if __name__ == "__main__":
    path = build()
    print(path)
    print(path.stat().st_size)
