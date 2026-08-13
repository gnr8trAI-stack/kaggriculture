from agents.v8_melon_optimizer import agent, tile_task


def plant(day_planted=0, watered=False, yield_units=1, consecutive=0, crop="MELON"):
    return {
        "kind": "PLANT",
        "crop": crop,
        "planted_day": day_planted,
        "watered_today": watered,
        "consecutive_unwatered": consecutive,
        "yield_units": yield_units,
    }


def observation(day=0, hour=0, tiles=None, seeds=0, money=3000, hands=None, shed=None, unlocked=None):
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "farms": [
            {
                "money": money,
                "tiles": tiles or [[None]],
                "farmer": [0, 0],
                "hands": hands or [],
                "hires_today": len(hands or []),
                "unlocked_quadrants": unlocked or ["NW"],
            },
            {
                "money": 3000,
                "tiles": [[None]],
                "farmer": [0, 0],
                "hands": [],
                "unlocked_quadrants": ["NW"],
            },
        ],
        "private": {
            "shed": shed or {},
            "seeds": {"MELON": seeds},
            "inventories": [{}],
        },
        "market": {"prices": {"MELON": 250}},
        "town": {"unlocked_shops": []},
    }


def test_new_melon_is_watered_not_harvested():
    assert tile_task(plant(day_planted=0, yield_units=1), day=0) == (2, ["WATER"])


def test_at_risk_melon_has_top_priority():
    assert tile_task(plant(day_planted=0, consecutive=1), day=3) == (0, ["WATER"])


def test_melon_waits_until_max_yield_day():
    assert tile_task(plant(day_planted=0, watered=True, yield_units=5), day=10) is None
    assert tile_task(plant(day_planted=0, watered=True, yield_units=6), day=12) == (1, ["HARVEST"])


def test_agent_buys_melon_seed_and_hires_initial_workforce():
    action = agent(observation(seeds=0))
    assert ["BUY_SEED", "MELON", 1] in action["market"]
    assert sum(order == ["HIRE"] for order in action["market"]) == 5


def test_agent_plants_melon_when_seed_available():
    action = agent(observation(seeds=1))
    assert action["farmer"] == ["PLANT", "MELON"]


def test_agent_stops_planting_after_day_16():
    action = agent(observation(day=17, seeds=10))
    assert action["farmer"] == ["PASS"]
    assert not any(order[:2] == ["BUY_SEED", "MELON"] for order in action["market"])


def test_agent_expands_once_in_first_harvest_window():
    action = agent(observation(day=10, money=1500, unlocked=["NW"]))
    assert ["BUY_LAND"] in action["market"]


def test_agent_does_not_expand_twice():
    action = agent(observation(day=10, money=5000, unlocked=["NW", "NE"]))
    assert ["BUY_LAND"] not in action["market"]


def test_agent_sells_all_inventory():
    action = agent(observation(shed={"MELON": 6}))
    assert ["SELL", "MELON", 6] in action["market"]
