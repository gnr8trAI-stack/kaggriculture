from agents.v5_task_routing import _assign_unit_v5, agent


def plant(yield_units=0, watered_today=False):
    return {
        "kind": "PLANT",
        "yield_units": yield_units,
        "watered_today": watered_today,
    }


def test_nearby_water_beats_distant_harvest_when_total_cost_is_lower():
    tiles = [[None for _ in range(7)] for _ in range(2)]
    tiles[0][6] = plant(yield_units=1, watered_today=True)
    tiles[1][0] = plant(yield_units=0, watered_today=False)
    targets = [(0, (6, 0), ["HARVEST"]), (1, (0, 1), ["WATER"])]
    action = _assign_unit_v5(tiles, (0, 0), targets, set(), False)
    assert action == ["SOUTH"]


def test_harvest_still_beats_water_at_similar_distance():
    tiles = [[None for _ in range(3)] for _ in range(2)]
    tiles[0][2] = plant(yield_units=1, watered_today=True)
    tiles[1][0] = plant(yield_units=0, watered_today=False)
    targets = [(0, (2, 0), ["HARVEST"]), (1, (0, 1), ["WATER"])]
    action = _assign_unit_v5(tiles, (0, 0), targets, set(), False)
    assert action == ["EAST"]


def test_executes_task_when_already_on_target():
    tiles = [[plant(yield_units=1, watered_today=True)]]
    targets = [(0, (0, 0), ["HARVEST"])]
    assert _assign_unit_v5(tiles, (0, 0), targets, set(), False) == ["HARVEST"]


def test_preserves_v2_seed_buying_and_market_shape():
    observation = {
        "player": 0,
        "day": 5,
        "hour": 12,
        "farms": [
            {"money": 3000, "tiles": [[None]], "farmer": [0, 0], "hands": []},
            {"money": 3000, "tiles": [[None]], "farmer": [0, 0], "hands": []},
        ],
        "private": {"shed": {}, "seeds": {"WHEAT": 0}},
        "market": {"prices": {}},
    }
    action = agent(observation)
    assert action["farmer"] == ["PASS"]
    assert ["BUY_SEED", "WHEAT", 2] in action["market"]
