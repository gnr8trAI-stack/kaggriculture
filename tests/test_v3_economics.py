from agents.v3_season_aware import (
    _add_seed_order,
    _replace_plant_actions,
    choose_crop,
    crop_score,
)


def observation(day=0, money=3000, prices=None, seeds=None):
    return {
        "player": 0,
        "day": day,
        "farms": [{"money": money}, {"money": 3000}],
        "market": {"prices": prices or {}},
        "private": {"seeds": seeds or {}},
    }


def test_crop_score_rejects_crop_too_late_in_season():
    assert crop_score("MELON", 25, 250) == float("-inf")


def test_low_cash_returns_no_crop():
    assert choose_crop(observation(money=100)) is None


def test_high_melon_price_can_justify_melon_early():
    crop = choose_crop(observation(day=0, prices={"MELON": 400, "WHEAT": 20}))
    assert crop == "MELON"


def test_late_season_prefers_fast_crop():
    crop = choose_crop(
        observation(
            day=26,
            prices={
                "WHEAT": 25,
                "CARROT": 35,
                "TOMATO": 200,
                "STRAWBERRY": 300,
                "MELON": 500,
            },
        )
    )
    assert crop in {"WHEAT", "CARROT"}


def test_glutted_premium_crop_is_penalized():
    crop = choose_crop(
        observation(
            day=0,
            prices={"WHEAT": 30, "CARROT": 35, "MELON": 100, "STRAWBERRY": 50},
        )
    )
    assert crop not in {"MELON", "STRAWBERRY"}


def test_plant_is_not_replaced_without_target_seed():
    action = {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": []}
    assert _replace_plant_actions(action, "MELON", available=0) == 0
    assert action["farmer"] == ["PLANT", "WHEAT"]


def test_replacement_count_never_exceeds_available_seed():
    action = {
        "farmer": ["PLANT", "WHEAT"],
        "hands": [["PLANT", "WHEAT"], ["PLANT", "WHEAT"]],
        "market": [],
    }
    assert _replace_plant_actions(action, "MELON", available=1) == 1
    planted = [action["farmer"], *action["hands"]]
    assert planted.count(["PLANT", "MELON"]) == 1


def test_premium_seed_order_does_not_remove_wheat_safety_order():
    action = {
        "farmer": ["PASS"],
        "hands": [],
        "market": [["BUY_SEED", "WHEAT", 2]],
    }
    _add_seed_order(action, observation(seeds={"MELON": 0}), "MELON")
    assert ["BUY_SEED", "WHEAT", 2] in action["market"]
    assert ["BUY_SEED", "MELON", 1] in action["market"]
