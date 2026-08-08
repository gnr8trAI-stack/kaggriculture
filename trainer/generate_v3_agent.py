"""Embed a replay-mined economic policy into the standalone v3 agent."""
from __future__ import annotations

import argparse
import json
import pprint
import re
from pathlib import Path

START = "# BEGIN LEARNED_POLICY"
END = "# END LEARNED_POLICY"


def generate(template: Path, policy_path: Path, output: Path) -> None:
    source = template.read_text(encoding="utf-8")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    runtime_policy = {
        "primary_crop": policy["primary_crop"],
        "primary_animal": policy.get("primary_animal", "COW"),
        "weed_soft_ratio": policy["weed_soft_ratio"],
        "weed_hard_ratio": policy["weed_hard_ratio"],
        "phases": policy["phases"],
    }
    block = f"{START}\nPOLICY = {pprint.pformat(runtime_policy, width=120, sort_dicts=True)}\n{END}"
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    rendered, count = pattern.subn(block, source, count=1)
    if count != 1:
        raise RuntimeError("learned-policy markers not found exactly once")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(json.dumps({"output": str(output), "bytes": output.stat().st_size, **runtime_policy}, default=str, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--template", type=Path, default=Path("agents/v3_economic.py"))
    p.add_argument("--policy", type=Path, default=Path("artifacts/economic_policy.json"))
    p.add_argument("--output", type=Path, default=Path("dist/main.py"))
    args = p.parse_args()
    generate(args.template, args.policy, args.output)
