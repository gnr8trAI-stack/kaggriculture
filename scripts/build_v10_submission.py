"""Build the exact standalone V10 Kaggriculture submission."""
from pathlib import Path


def build() -> Path:
    root = Path(__file__).resolve().parents[1]
    source = root / "agents" / "v10_market_front_runner.py"
    output = root / "dist" / "submission.py"
    output.parent.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8")
    output.write_text(
        '"""Standalone Kaggriculture V10 competition submission."""\n\n' + text,
        encoding="utf-8",
    )
    return output


if __name__ == "__main__":
    path = build()
    print(path)
    print(path.stat().st_size)
