from scripts.benchmark import GameResult, summarize


def result(delta: float, status: str = "DONE") -> GameResult:
    return GameResult(
        seed=0,
        candidate_seat=0,
        candidate_reward=100 + delta,
        opponent_reward=100,
        delta=delta,
        candidate_status=status,
        opponent_status="DONE",
        elapsed_seconds=1.0,
    )


def test_summary_counts_and_statistics():
    summary = summarize([result(20), result(0), result(-10)])
    assert summary.games == 3
    assert summary.wins == 1
    assert summary.ties == 1
    assert summary.losses == 1
    assert summary.mean_delta == 10 / 3
    assert summary.median_delta == 0
    assert summary.invalid_or_error_games == 0


def test_summary_flags_invalid_games():
    summary = summarize([result(0, status="INVALID")])
    assert summary.invalid_or_error_games == 1
