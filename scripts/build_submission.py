"""Build a single-file Kaggle submission from the dependency-free agent."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "agents" / "adaptive_agent.py"
DIST = ROOT / "dist"
OUTPUT = DIST / "submission.py"

DIST.mkdir(exist_ok=True)
OUTPUT.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
print(OUTPUT)
