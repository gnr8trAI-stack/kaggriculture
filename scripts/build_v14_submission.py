"""Build the standalone V14 integrated-farm Kaggriculture submission."""
from pathlib import Path

from scripts.build_v13_submission import _v12_source


def build() -> Path:
    root = Path(__file__).resolve().parents[1]
    v10 = (root / "agents" / "v10_market_front_runner.py").read_text(encoding="utf-8")
    v12 = _v12_source(root)
    wrapper = (root / "agents" / "v14_integrated_farm.py").read_text(encoding="utf-8")
    body = wrapper[wrapper.index("Position ="):]
    output = root / "dist" / "submission.py"
    output.parent.mkdir(parents=True, exist_ok=True)
    text = f'''"""Standalone Kaggriculture V14 integrated-farm submission."""
from collections import Counter, deque
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
import time

_V10_SOURCE = {v10!r}
_V12_SOURCE = {v12!r}
_v10_ns = {{"__name__": "_v10_embedded"}}
_v12_ns = {{"__name__": "_v12_embedded"}}
exec(_V10_SOURCE, _v10_ns)
exec(_V12_SOURCE, _v12_ns)
v10_agent = _v10_ns["agent"]
v12_agent = _v12_ns["agent"]

{body}
'''
    output.write_text(text, encoding="utf-8")
    return output


if __name__ == "__main__":
    path = build()
    print(path)
    print(path.stat().st_size)
