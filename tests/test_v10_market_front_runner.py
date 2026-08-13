from agents import v10_market_front_runner as v10


def plant(planted_day=0, watered=True, yield_units=6, consecutive=0):
    return {
        "kind": "PLANT",
        "crop": "MELON",
        "planted_day": planted_day,
        "watered_today": watered,
        "consecutive_unwatered": consecutive,
        "yield_units": yield_units,
    }


def observation(day=0, hour=0, tiles=None, seeds=0, inventory=None, hands=None, shed=None):
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "farms": [
            {
                "money": 3000,
                "tiles": tiles or [[None]],
                "farmer": [0, 0],
                "hands": hands or [],
                "unlocked_quadrants": ["NW"],
            },
            {
                "money": 3000,
                "tiles": [[None]],
                "farmer": [0, 0],
                "hands": [],
                "unlocked_quadrants": ["SE"],
            },
        ],
        "private": {
            "shed": shed or {},
            "seeds": {"MELON": seeds},
            "inventories": [inventory or {}],
        },
        "market": {"prices": {"MELON": 250}, "inventory": {"MELON": 10000}},
        "town": {"unlocked_shops": []},
    }


def test_melon_harvests_at_true_max_yield_day_10():
    assert v10.tile_task(plant(planted_day=0), day=9) is None
    assert v10.tile_task(plant(planted_day=0), day=10) == (1, ["HARVEST"])


def test_at_risk_watering_outranks_harvest():
    tile = plant(planted_day=0, watered=False, yield_units=6, consecutive=1)
    assert v10.tile_task(tile, day=10) == (0, ["WATER"])


def test_loaded_unit_drops_when_on_shed_cell():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    obs = observation(day=10, hour=12, tiles=tiles, inventory={"MELON": 6})
    obs["farms"][0]["farmer"] = [4, 4]
    assert v10.agent(obs)["farmer"] == ["DROP"]


def test_loaded_unit_routes_to_shed_mid_day():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    obs = observation(day=10, hour=12, tiles=tiles, inventory={"MELON": 6})
    obs["farms"][0]["farmer"] = [0, 0]
    assert v10.agent(obs)["farmer"][0] in {"SOUTH", "EAST"}


def test_agent_sells_shed_and_buys_seed():
    action = v10.agent(observation(seeds=0, shed={"MELON": 6}))
    assert ["SELL", "MELON", 6] in action["market"]
    assert any(order[:2] == ["BUY_SEED", "MELON"] for order in action["market"])


def test_no_land_expansion():
    action = v10.agent(observation())
    assert not any(order[:1] == ["BUY_LAND"] for order in action["market"])
