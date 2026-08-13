from agents.v7_lifecycle_core import agent, tile_task


def plant(day_planted=0, watered=False, yield_units=1, crop="CARROT", consecutive=0):
    return {
        "kind": "PLANT",
        "crop": crop,
        "planted_day": day_planted,
        "watered_today": watered,
        "consecutive_unwatered": consecutive,
        "yield_units": yield_units,
    }


def observation(day=0, hour=0, tiles=None, seeds=0, money=3000, hands=None, shed=None):
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
            },
            {"money": 3000, "tiles": [[None]], "farmer": [0, 0], "hands": []},
        ],
        "private": {
            "shed": shed or {},
            "seeds": {"CARROT": seeds},
            "inventories": [{}],
        },
        "market": {"prices": {"CARROT": 35}},
        "town": {"unlocked_shops": []},
    }


def test_immature_initial_yield_is_watered_not_harvested():
    assert tile_task(plant(day_planted=0, yield_units=1), day=0) == (2, ["WATER"])


def test_mature_carrot_is_harvested():
    assert tile_task(plant(day_planted=0, watered=True, yield_units=3), day=3) == (0, ["HARVEST"])


def test_at_risk_crop_gets_urgent_water_priority():
    assert tile_task(plant(consecutive=1), day=1) == (1, ["WATER"])


def test_agent_plants_when_seed_available():
    action = agent(observation(seeds=1))
    assert action["farmer"] == ["PLANT", "CARROT"]


def test_agent_buys_carrot_seed_and_hires_hands():
    action = agent(observation(seeds=0))
    assert any(order[:2] == ["BUY_SEED", "CARROT"] for order in action["market"])
    assert sum(order == ["HIRE"] for order in action["market"]) == 5


def test_agent_sells_inventory():
    action = agent(observation(shed={"CARROT": 7}))
    assert ["SELL", "CARROT", 7] in action["market"]


def test_no_new_planting_after_day_26():
    action = agent(observation(day=27, seeds=10))
    assert action["farmer"] == ["PASS"]
    assert not any(order[:2] == ["BUY_SEED", "CARROT"] for order in action["market"])
