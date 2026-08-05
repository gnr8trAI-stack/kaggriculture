import importlib.util
from agents import v14_integrated_farm as v14
from scripts.build_v14_submission import build


def tiles(unlock_ne=False):
    board = [["LOCKED" for _ in range(10)] for _ in range(10)]
    for y in range(5):
        for x in range(5):
            board[y][x] = None
    if unlock_ne:
        for y in range(5):
            for x in range(5, 10):
                board[y][x] = None
    return board


def obs(day=0, unlock_ne=False, money=3000, opponent_melons=0, melon_price=250, melon_inventory=10000):
    own = tiles(unlock_ne)
    other = tiles()
    for i in range(opponent_melons):
        y, x = divmod(i, 5)
        other[y][x] = {"kind": "PLANT", "crop": "MELON", "planted_day": 0, "watered_today": True, "yield_units": 1}
    return {
        "player": 0, "step": day * 24, "day": day, "hour": 0,
        "farms": [
            {"money": money, "tiles": own, "farmer": [4, 4], "hands": [], "unlocked_quadrants": ["NW", "NE"] if unlock_ne else ["NW"]},
            {"money": 3000, "tiles": other, "farmer": [4, 4], "hands": [], "unlocked_quadrants": ["NW"]},
        ],
        "market": {"prices": {"WHEAT": 25, "MELON": melon_price, "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100}, "inventory": {"MELON": melon_inventory}},
        "town": {"unlocked_shops": []},
        "private": {"shed": {}, "seeds": {}, "inventories": [{}]},
    }


def test_does_not_abandon_v10_before_first_harvest():
    v14.reset_state()
    action = v14.agent(obs(day=0, opponent_melons=20, melon_price=100, melon_inventory=10100))
    assert set(action) == {"farmer", "hands", "market"}
    assert v14.get_telemetry()[-1]["mode"] == "v10"


def test_switch_requires_two_signals_after_day_ten():
    v14.reset_state()
    v14.agent(obs(day=10, opponent_melons=16, melon_price=160))
    record = v14.get_telemetry()[-1]
    assert record["regime"]["risk_score"] >= 2
    assert record["mode"] == "v12"


def test_land_purchase_is_cash_and_utilization_gated():
    v14.reset_state()
    state = obs(day=10, money=12000)
    for y in range(4):
        for x in range(5):
            state["farms"][0]["tiles"][y][x] = {"kind": "PLANT", "crop": "MELON", "planted_day": 0, "watered_today": True, "yield_units": 1}
    action = v14.agent(state)
    assert ["BUY_LAND"] in action["market"]


def test_unlocked_land_starts_animal_program():
    v14.reset_state()
    action = v14.agent(obs(day=10, unlock_ne=True, money=12000))
    record = v14.get_telemetry()[-1]
    assert record["animal"]["plan"] in {"GOOSE", "COW", "SHEEP"}
    assert action["farmer"][0] in {"EAST", "SOUTH", "BUILD_COOP", "BUILD_PASTURE"}


def test_standalone_v14_compiles_and_runs():
    path = build()
    text = path.read_text(encoding="utf-8")
    assert "from agents" not in text
    assert "from scripts" not in text
    spec = importlib.util.spec_from_file_location("v14_submission", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    action = module.agent(obs())
    assert set(action) == {"farmer", "hands", "market"}
