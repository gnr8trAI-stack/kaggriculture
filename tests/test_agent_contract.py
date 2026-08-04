from agents.adaptive_agent import agent


def mock_observation():
    tiles = [[None for _ in range(10)] for _ in range(10)]
    return {
        "player": 0,
        "day": 0,
        "hour": 0,
        "farms": [
            {"money": 3000, "tiles": tiles, "farmer": [0, 0], "hands": []},
            {"money": 3000, "tiles": tiles, "farmer": [0, 0], "hands": []},
        ],
        "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
        "market": {"prices": {}, "inventory": {}},
        "town": {"unlocked_shops": []},
    }


def test_action_contract():
    action = agent(mock_observation())
    assert set(action) == {"farmer", "hands", "market"}
    assert isinstance(action["farmer"], list)
    assert isinstance(action["hands"], list)
    assert isinstance(action["market"], list)
    assert len(action["market"]) <= 10


def test_missing_observation_fails_safe():
    assert agent({}) == {"farmer": ["PASS"], "hands": [], "market": []}


def test_final_day_liquidates_inventory():
    obs = mock_observation()
    obs["day"] = 29
    obs["private"]["shed"] = {"MELON": 3, "WHEAT": 2}
    orders = agent(obs)["market"]
    assert ["SELL", "MELON", 3] in orders
    assert ["SELL", "WHEAT", 2] in orders
