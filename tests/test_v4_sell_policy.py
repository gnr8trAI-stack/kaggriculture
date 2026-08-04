from agents.v4_sell_policy import agent, sell_orders


def observation(day=5, hour=12, shed=None, prices=None, wheat_seeds=0, money=3000):
    return {
        "player": 0,
        "day": day,
        "hour": hour,
        "farms": [
            {
                "money": money,
                "tiles": [[None]],
                "farmer": [0, 0],
                "hands": [],
            },
            {"money": 3000, "tiles": [[None]], "farmer": [0, 0], "hands": []},
        ],
        "private": {
            "shed": shed or {},
            "seeds": {"WHEAT": wheat_seeds},
        },
        "market": {"prices": prices or {}},
    }


def test_sells_single_unit_at_reference_price():
    orders = sell_orders(observation(shed={"WHEAT": 1}, prices={"WHEAT": 25}))
    assert orders == [["SELL", "WHEAT", 1]]


def test_holds_small_lot_when_price_is_below_reference_early():
    orders = sell_orders(observation(shed={"WHEAT": 3}, prices={"WHEAT": 20}))
    assert orders == []


def test_sells_four_units_even_when_price_is_low():
    orders = sell_orders(observation(shed={"WHEAT": 4}, prices={"WHEAT": 20}))
    assert orders == [["SELL", "WHEAT", 4]]


def test_late_season_sells_any_positive_inventory():
    orders = sell_orders(observation(day=24, shed={"WHEAT": 1}, prices={"WHEAT": 10}))
    assert orders == [["SELL", "WHEAT", 1]]


def test_final_liquidation_sells_all_products():
    orders = sell_orders(
        observation(day=29, shed={"WHEAT": 2, "CARROT": 1}, prices={"WHEAT": 1, "CARROT": 1})
    )
    assert ["SELL", "WHEAT", 2] in orders
    assert ["SELL", "CARROT", 1] in orders


def test_preserves_v2_seed_purchase_order():
    action = agent(observation(shed={"WHEAT": 1}, prices={"WHEAT": 25}, wheat_seeds=0))
    assert ["SELL", "WHEAT", 1] in action["market"]
    assert any(order[:2] == ["BUY_SEED", "WHEAT"] for order in action["market"])
