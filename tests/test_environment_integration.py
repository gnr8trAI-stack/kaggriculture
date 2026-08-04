"""Smoke tests against the installed official Kaggle environment package."""

from kaggle_environments import make

from agents.adaptive_agent import agent


def test_kaggriculture_environment_is_registered():
    env = make("kaggriculture", configuration={"episodeSteps": 2, "seed": 1}, debug=True)
    assert env.name == "kaggriculture"
    assert env.configuration.episodeSteps == 2


def test_agent_completes_short_real_episode():
    env = make("kaggriculture", configuration={"episodeSteps": 4, "seed": 7}, debug=True)
    env.run([agent, agent])

    assert len(env.steps) >= 2
    assert all(state.status not in {"ERROR", "INVALID", "TIMEOUT"} for state in env.state)
