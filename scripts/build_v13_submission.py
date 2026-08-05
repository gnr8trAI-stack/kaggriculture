"""Build a standalone V13 hybrid Kaggriculture submission."""
from pathlib import Path


def _v12_source(root: Path) -> str:
    planner = (root / "agents" / "v11_adaptive_planner.py").read_text(encoding="utf-8")
    overlay = (root / "agents" / "v12_market_aware.py").read_text(encoding="utf-8")
    start = overlay.index("MARKET_PARAMS =")
    end = overlay.index("# V11's agent resolves choose_crop")
    body = overlay[start:end]
    for old, new in {
        "planner.CROPS": "CROPS",
        "planner._mapping": "_mapping",
        "planner._crop_counts": "_crop_counts",
        "planner._remaining_days": "_remaining_days",
        "planner.ENDGAME_BUFFER_DAYS": "ENDGAME_BUFFER_DAYS",
    }.items():
        body = body.replace(old, new)
    return planner + "\n\nimport math\n\n" + body


def build() -> Path:
    root = Path(__file__).resolve().parents[1]
    v10 = (root / "agents" / "v10_market_front_runner.py").read_text(encoding="utf-8")
    v12 = _v12_source(root)
    output = root / "dist" / "submission.py"
    output.parent.mkdir(parents=True, exist_ok=True)
    text = f'''"""Standalone Kaggriculture V13 conservative hybrid submission."""
from collections import Counter
from typing import Mapping

_V10_SOURCE = {v10!r}
_V12_SOURCE = {v12!r}
_v10_ns = {{"__name__": "_v10_embedded"}}
_v12_ns = {{"__name__": "_v12_embedded"}}
exec(_V10_SOURCE, _v10_ns)
exec(_V12_SOURCE, _v12_ns)
_MODE = "v10"
_LAST_STEP = -1


def _m(value):
    return value if isinstance(value, Mapping) else {{}}


def _counts(tiles):
    result = Counter()
    if not isinstance(tiles, list):
        return result
    for row in tiles:
        if not isinstance(row, list):
            continue
        for tile in row:
            if isinstance(tile, Mapping) and str(tile.get("kind", tile.get("type", ""))).upper() == "PLANT":
                result[str(tile.get("crop", "")).upper()] += 1
    return result


def agent(observation, configuration=None):
    global _MODE, _LAST_STEP
    obs = observation if isinstance(observation, dict) else {{k: getattr(observation, k) for k in ("player", "day", "hour", "farms", "market", "town", "private") if hasattr(observation, k)}}
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    step = day * 24 + hour
    if _LAST_STEP >= 0 and step <= _LAST_STEP:
        _MODE = "v10"
    _LAST_STEP = step
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", [])
    opponent = _m(farms[1 - player]) if isinstance(farms, list) and len(farms) > 1 else {{}}
    opponent_melons = int(_counts(opponent.get("tiles", [])).get("MELON", 0))
    market = _m(obs.get("market"))
    prices = _m(market.get("prices"))
    inventory = _m(market.get("inventory"))
    melon_price = float(prices.get("MELON", 250) or 250)
    melon_inventory = float(inventory.get("MELON", 10000) or 10000)
    if _MODE == "v10" and (opponent_melons >= 12 or melon_price <= 120 or melon_inventory >= 10180):
        _MODE = "v12"
    policy = _v10_ns["agent"] if _MODE == "v10" else _v12_ns["agent"]
    action = dict(policy(obs, configuration))
    return {{"farmer": action.get("farmer", ["PASS"]), "hands": action.get("hands", []), "market": action.get("market", [])}}
'''
    output.write_text(text, encoding="utf-8")
    return output


if __name__ == "__main__":
    path = build()
    print(path)
    print(path.stat().st_size)
