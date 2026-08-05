import importlib.util
from pathlib import Path

from agents import v12_agent
from agents import v12_market_aware as v12
from agents.v11_adaptive_planner import CROPS
from scripts.build_v12_submission import build


def blank_tiles():
    tiles = [["LOCKED" for _ in range(10)] for _ in range(10)]
    for y in range(5):
        for x in range(5):
            tiles[y][x] = None
    return tiles


def observation(day=0, prices=None, inventory=None, opponent_tiles=None, seeds=None):
    return {
        "player": 0,
        "day": day,
        "hour": 0,
        "farms": [
            {"money": 3000, "tiles": blank_tiles(), "farmer": [0, 0], "hands": []},
            {"money": 3000, "tiles": opponent_tiles or blank_tiles(), "farmer": [0, 0], "hands": []},
        ],
        "market": {
            "prices": prices or {name: data["base"] for name, data in CROPS.items()},
            "inventory": inventory or {name: 10000 for name in CROPS},
        },
        "town": {"unlocked_shops": []},
        "private": {"shed": {}, "seeds": seeds or {}, "inventories": [{}]},
    }


def test_documented_melon_curve_reaches_floor_at_one_throughput():
    assert v12.projected_price("MELON", 10300) == 1


def test_opening_policy_preserves_proven_melon_economics():
    obs = observation()
    crop, scores = v12.choose_crop(obs, obs["farms"][0])
    assert crop == "MELON"
    assert scores["MELON"] > scores["WHEAT"]


def test_visible_melon_crowding_can_force_diversification():
    opponent = blank_tiles()
    for y in range(3):
        for x in range(5):
            opponent[y][x] = {
                "kind": "PLANT",
                "crop": "MELON",
                "planted_day": 0,
                "watered_today": True,
                "consecutive_unwatered": 0,
                "yield_units": 0,
            }
    obs = observation(opponent_tiles=opponent)
    crop, _ = v12.choose_crop(obs, obs["farms"][0])
    assert crop != "MELON"


def test_submission_wrapper_returns_legal_schema_and_telemetry():
    v12_agent.reset_telemetry()
    action = v12_agent.agent(observation(seeds={"MELON": 1}))
    assert set(action) == {"farmer", "hands", "market"}
    records = v12_agent.get_telemetry(clear=True)
    assert records
    assert records[-1]["planner"]["selected_crop"] == "MELON"


def test_standalone_v12_build_imports_and_runs():
    path = build()
    text = path.read_text(encoding="utf-8")
    assert "from agents" not in text
    assert "import agents" not in text
    spec = importlib.util.spec_from_file_location("v12_submission", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    action = module.agent(observation(seeds={"MELON": 1}))
    assert set(action) >= {"farmer", "hands", "market"}
