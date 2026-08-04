from agents.v6_seed_throughput import agent, desired_seed_buffer


def observation(day=5, hour=12, wheat_seeds=0, money=3000, hands=None):
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "farms": [
            {
                "money": money,
                "tiles": [[None]],
                "farmer": [0, 0],
                "hands": hands or [],
            },
            {"money": 3000, "tiles": [[None]], "farmer": [0, 0], "hands": []},
        ],
        "private": {"shed": {}, "seeds": {"WHEAT": wheat_seeds}},
        "market": {"prices": {}},
    }


def test_early_buffer_exceeds_v2_baseline():
    assert desired_seed_buffer(5, 0) == 4


def test_buffer_tapers_with_season():
    assert desired_seed_buffer(22, 0) == 3
    assert desired_seed_buffer(27, 0) == 2


def test_early_game_buys_four_seeds_from_zero():
    action = agent(observation(day=5, wheat_seeds=0, money=3000))
    assert ["BUY_SEED", "WHEAT", 4] in action["market"]


def test_purchase_is_limited_by_cash():
    action = agent(observation(day=5, wheat_seeds=0, money=20))
    assert ["BUY_SEED", "WHEAT", 2] in action["market"]


def test_does_not_buy_during_liquidation():
    action = agent(observation(day=29, wheat_seeds=0, money=3000))
    assert not any(order[:2] == ["BUY_SEED", "WHEAT"] for order in action["market"])
