from agents import v9_portfolio_optimizer as v9


def plant(crop="MELON", planted_day=0, watered=False, yield_units=1, consecutive=0):
    return {
        "kind": "PLANT",
        "crop": crop,
        "planted_day": planted_day,
        "watered_today": watered,
        "consecutive_unwatered": consecutive,
        "yield_units": yield_units,
    }


def observation(day=0, tiles=None, opponent_tiles=None, seeds=None, money=3000, hands=None, shed=None):
    return {
        "player": 0,
        "day": day,
        "hour": 0,
        "farms": [
            {"money": money, "tiles": tiles or [[None]], "farmer": [0, 0], "hands": hands or []},
            {"money": 3000, "tiles": opponent_tiles or [[None]], "farmer": [0, 0], "hands": []},
        ],
        "private": {
            "shed": shed or {},
            "seeds": seeds or {"MELON": 0, "TOMATO": 0},
            "inventories": [{}],
        },
        "market": {"prices": {"MELON": 250, "TOMATO": 120}},
        "town": {"unlocked_shops": []},
    }


def test_at_risk_crop_is_watered_first():
    assert v9.tile_task(plant(consecutive=1), day=1) == (0, ["WATER"])


def test_melon_waits_for_max_yield_day():
    assert v9.tile_task(plant(planted_day=0, watered=True, yield_units=4), day=10) is None
    assert v9.tile_task(plant(planted_day=0, watered=True, yield_units=6), day=12) == (1, ["HARVEST"])


def test_tomato_harvests_from_first_ongoing_yield_day():
    assert v9.tile_task(plant(crop="TOMATO", planted_day=0, watered=True, yield_units=1), day=8) == (1, ["HARVEST"])


def test_opponent_melon_commitment_reduces_our_melon_share():
    own = [[plant("MELON") for _ in range(3)] + [plant("TOMATO") for _ in range(2)]]
    opponent = [[plant("MELON") for _ in range(12)]]
    assert v9._choose_crop(own, opponent, day=1) == "TOMATO"


def test_agent_uses_available_seed_and_sells():
    action = v9.agent(observation(seeds={"MELON": 1, "TOMATO": 0}, shed={"MELON": 4}))
    assert action["farmer"] == ["PLANT", "MELON"]
    assert ["SELL", "MELON", 4] in action["market"]


def test_no_land_expansion_order():
    action = v9.agent(observation(money=100000))
    assert not any(order[:1] == ["BUY_LAND"] for order in action["market"])
