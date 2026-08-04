from agents.v3b_conservative import (
    CASH_RESERVE,
    MAX_PREMIUM_SEEDS,
    agent,
    choose_premium_crop,
    expected_profit,
)


def observation(day=0, money=3000, prices=None, seeds=None, tiles=None):
    return {
        "player": 0,
        "day": day,
        "hour": 0,
        "farms": [
            {
                "money": money,
                "farmer": [0, 0],
                "hands": [],
                "tiles": tiles if tiles is not None else [[None]],
            },
            {"money": 3000, "farmer": [0, 0], "hands": [], "tiles": [[None]]},
        ],
        "private": {
            "seeds": seeds or {"WHEAT": 2},
            "shed": {},
        },
        "market": {"prices": prices or {}},
    }


def test_wheat_remains_default_without_premium_inventory():
    obs = observation(prices={"MELON": 500}, seeds={"WHEAT": 2, "MELON": 0})
    action = agent(obs)
    assert action["farmer"] == ["PLANT", "WHEAT"]


def test_existing_premium_seed_can_replace_wheat_when_advantage_is_large():
    obs = observation(
        prices={"WHEAT": 20, "MELON": 500},
        seeds={"WHEAT": 2, "MELON": 1},
    )
    assert choose_premium_crop(obs) == "MELON"
    action = agent(obs)
    assert action["farmer"] == ["PLANT", "MELON"]


def test_low_cash_blocks_premium_crop_use():
    obs = observation(
        money=CASH_RESERVE - 1,
        prices={"WHEAT": 20, "MELON": 500},
        seeds={"WHEAT": 2, "MELON": 1},
    )
    assert choose_premium_crop(obs) is None


def test_long_crop_rejected_late_in_season():
    obs = observation(
        day=20,
        prices={"WHEAT": 20, "MELON": 500},
        seeds={"WHEAT": 2, "MELON": 1},
    )
    assert expected_profit(obs, "MELON") == float("-inf")
    assert choose_premium_crop(obs) is None


def test_premium_purchase_is_single_seed_and_preserves_wheat_order():
    obs = observation(
        day=0,
        money=3000,
        prices={"WHEAT": 20, "MELON": 500},
        seeds={"WHEAT": 0, "MELON": 0},
        tiles=[[{"kind": "PLANT", "watered_today": True}]],
    )
    action = agent(obs)
    assert ["BUY_SEED", "WHEAT", 2] in action["market"]
    assert not any(order[:2] == ["BUY_SEED", "MELON"] for order in action["market"])


def test_premium_inventory_cap_prevents_more_buying():
    obs = observation(
        day=0,
        money=3000,
        prices={"WHEAT": 20, "MELON": 500},
        seeds={"WHEAT": 2, "MELON": MAX_PREMIUM_SEEDS},
        tiles=[[{"kind": "PLANT", "watered_today": True}]],
    )
    action = agent(obs)
    premium_orders = [
        order for order in action["market"] if order[:2] == ["BUY_SEED", "MELON"]
    ]
    assert premium_orders == []
