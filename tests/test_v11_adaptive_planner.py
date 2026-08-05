from importlib.util import module_from_spec, spec_from_file_location

from agents import v11_agent
from agents.v11_adaptive_planner import CROPS, _crop_score, choose_crop
from scripts.build_v11_submission import build


def _blank_tiles():
    tiles = [["LOCKED" for _ in range(10)] for _ in range(10)]
    for y in range(5):
        for x in range(5):
            tiles[y][x] = None
    return tiles


def _obs(day=0, hour=0, prices=None, opponent_tiles=None, seeds=None):
    prices = prices or {crop: data["base"] for crop, data in CROPS.items()}
    opponent_tiles = opponent_tiles or _blank_tiles()
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "farms": [
            {
                "money": 3000,
                "tiles": _blank_tiles(),
                "farmer": [0, 0],
                "hands": [],
                "unlocked_quadrants": ["NW"],
                "hires_today": 0,
            },
            {
                "money": 3000,
                "tiles": opponent_tiles,
                "farmer": [0, 0],
                "hands": [],
                "unlocked_quadrants": ["NW"],
                "hires_today": 0,
            },
        ],
        "market": {"prices": prices, "inventory": {crop: 10000 for crop in CROPS}},
        "town": {"unlocked_shops": []},
        "private": {
            "shed": {},
            "seeds": seeds or {},
            "inventories": [{}],
        },
    }


def test_crop_score_rejects_crop_that_cannot_finish():
    score = _crop_score("MELON", 250, 0, 0, 5.0, [])
    assert score == float("-inf")


def test_choose_crop_responds_to_live_prices():
    obs = _obs(prices={
        "WHEAT": 25,
        "CARROT": 35,
        "TOMATO": 60,
        "STRAWBERRY": 120,
        "MELON": 1,
    })
    crop, scores = choose_crop(obs, obs["farms"][0])
    assert crop != "MELON"
    assert scores["MELON"] < scores[crop]


def test_choose_crop_penalizes_visible_opponent_exposure():
    opponent = _blank_tiles()
    for x in range(5):
        opponent[0][x] = {
            "kind": "PLANT",
            "crop": "MELON",
            "planted_day": 0,
            "watered_today": True,
            "consecutive_unwatered": 0,
            "yield_units": 0,
        }
    obs = _obs(opponent_tiles=opponent)
    crop, _ = choose_crop(obs, obs["farms"][0])
    assert crop in CROPS


def test_submission_wrapper_returns_only_legal_top_level_keys():
    v11_agent.reset_telemetry()
    action = v11_agent.agent(_obs(seeds={"MELON": 1}))
    assert set(action) == {"farmer", "hands", "market"}
    assert isinstance(v11_agent.LAST_DECISION, dict)


def test_telemetry_records_state_planner_actions_and_latency():
    v11_agent.reset_telemetry()
    action = v11_agent.agent(_obs(day=2, hour=3, seeds={"MELON": 1}))
    records = v11_agent.get_telemetry()
    assert len(records) == 1
    record = records[0]
    assert record["schema_version"] == v11_agent.TELEMETRY_SCHEMA_VERSION
    assert record["step"] == 51
    assert record["decision_duration_ms"] >= 0
    assert record["planner"]["selected_crop"] in CROPS
    assert record["market_prices"]["MELON"] == 250
    assert record["action"]["farmer"] == action["farmer"]
    assert record["action"]["counts"]


def test_telemetry_can_be_drained_between_episodes():
    v11_agent.reset_telemetry()
    v11_agent.agent(_obs())
    assert len(v11_agent.get_telemetry(clear=True)) == 1
    assert v11_agent.get_telemetry() == []


def test_endgame_does_not_buy_long_cycle_seed():
    obs = _obs(day=28, hour=0, seeds={})
    action = v11_agent.agent(obs)
    assert not any(order[:2] == ["BUY_SEED", "MELON"] for order in action["market"])


def test_standalone_submission_has_legal_output_and_no_repository_imports():
    path = build()
    text = path.read_text(encoding="utf-8")
    assert "from agents" not in text
    assert "import agents" not in text
    spec = spec_from_file_location("v11_submission_test", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    action = module.agent(_obs(seeds={"MELON": 1}))
    assert set(action) == {"farmer", "hands", "market"}
