from agents.v3_season_aware import choose_crop, crop_score


def observation(day=0, money=3000, prices=None):
    return {
        "player": 0,
        "day": day,
        "farms": [{"money": money}, {"money": 3000}],
        "market": {"prices": prices or {}},
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
