from agents.adaptive_agent import agent


def observation(tiles, farmer=(0, 0), hands=None, seeds=0):
    hands = hands or []
    farm = {"money": 3000, "tiles": tiles, "farmer": list(farmer), "hands": hands}
    return {
        "player": 0,
        "day": 0,
        "hour": 0,
        "farms": [farm, dict(farm)],
        "private": {"shed": {}, "seeds": {"WHEAT": seeds}},
        "market": {},
        "town": {},
    }


def test_farmer_moves_toward_urgent_plant():
    tiles = [[None for _ in range(3)] for _ in range(3)]
    tiles[0][2] = {"kind": "PLANT", "yield_units": 1, "watered_today": True}
    result = agent(observation(tiles))
    assert result["farmer"] == ["EAST"]


def test_harvest_underfoot_is_immediate():
    tiles = [[None for _ in range(2)] for _ in range(2)]
    tiles[0][0] = {"kind": "PLANT", "yield_units": 2, "watered_today": True}
    result = agent(observation(tiles))
    assert result["farmer"] == ["HARVEST"]


def test_workers_reserve_different_targets():
    tiles = [[None for _ in range(3)] for _ in range(3)]
    tiles[0][2] = {"kind": "PLANT", "yield_units": 1, "watered_today": True}
    tiles[2][0] = {"kind": "PLANT", "yield_units": 1, "watered_today": True}
    result = agent(observation(tiles, farmer=(0, 0), hands=[[2, 2]]))
    assert result["farmer"] == ["EAST"]
    assert result["hands"] == [["WEST"]]


def test_planting_is_fallback_after_service_work():
    tiles = [[None for _ in range(2)] for _ in range(2)]
    tiles[1][1] = {"kind": "PLANT", "yield_units": 0, "watered_today": False}
    result = agent(observation(tiles, farmer=(0, 0), seeds=2))
    assert result["farmer"] in (["SOUTH"], ["EAST"])


def test_locked_cells_are_not_traversed():
    tiles = [
        [None, "LOCKED", {"kind": "PLANT", "yield_units": 1}],
        [None, "LOCKED", None],
        [None, None, None],
    ]
    result = agent(observation(tiles, farmer=(0, 0)))
    assert result["farmer"] == ["SOUTH"]
