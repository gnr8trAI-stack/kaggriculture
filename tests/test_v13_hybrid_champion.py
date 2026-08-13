import importlib.util
from pathlib import Path

from agents import v13_hybrid_champion as v13
from agents.v11_adaptive_planner import CROPS
from scripts.build_v13_submission import build


def blank_tiles():
    tiles = [["LOCKED" for _ in range(10)] for _ in range(10)]
    for y in range(5):
        for x in range(5):
            tiles[y][x] = None
    return tiles


def observation(opponent_melons=0, melon_price=250, melon_inventory=10000):
    opponent = blank_tiles()
    placed = 0
    for y in range(5):
        for x in range(5):
            if placed < opponent_melons:
                opponent[y][x] = {
                    "kind": "PLANT", "crop": "MELON", "planted_day": 0,
                    "watered_today": True, "consecutive_unwatered": 0,
                    "yield_units": 0,
                }
                placed += 1
    prices = {name: data["base"] for name, data in CROPS.items()}
    prices["MELON"] = melon_price
    inventory = {name: 10000 for name in CROPS}
    inventory["MELON"] = melon_inventory
    return {
        "player": 0, "day": 0, "hour": 0,
        "farms": [
            {"money": 3000, "tiles": blank_tiles(), "farmer": [0, 0], "hands": []},
            {"money": 3000, "tiles": opponent, "farmer": [0, 0], "hands": []},
        ],
        "market": {"prices": prices, "inventory": inventory},
        "town": {"unlocked_shops": []},
        "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
    }


def test_default_regime_uses_v10():
    v13.reset_state()
    action = v13.agent(observation())
    assert set(action) == {"farmer", "hands", "market"}
    assert v13.get_telemetry()[-1]["mode"] == "v10"


def test_heavy_visible_melon_regime_switches_to_v12():
    v13.reset_state()
    v13.agent(observation(opponent_melons=12))
    record = v13.get_telemetry()[-1]
    assert record["mode"] == "v12"
    assert record["switched_this_turn"] is True


def test_switch_is_one_way_within_episode():
    v13.reset_state()
    v13.agent(observation(opponent_melons=12))
    later = observation()
    later["hour"] = 1
    v13.agent(later)
    assert v13.get_telemetry()[-1]["mode"] == "v12"


def test_low_melon_price_switches_to_v12():
    v13.reset_state()
    v13.agent(observation(melon_price=100))
    assert v13.get_telemetry()[-1]["mode"] == "v12"


def test_standalone_build_compiles_and_runs():
    path = build()
    text = path.read_text(encoding="utf-8")
    assert "from agents" not in text
    spec = importlib.util.spec_from_file_location("v13_submission", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    action = module.agent(observation())
    assert set(action) == {"farmer", "hands", "market"}
