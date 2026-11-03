import pytest
from kb_agent.config import REQUIRED, missing_settings, require_settings

GOOD = {name: "real-value" for name in REQUIRED}


def test_a_complete_environment_passes() -> None:
    assert missing_settings(GOOD) == []
    require_settings(GOOD)


def test_missing_and_placeholder_values_stop_the_worker_with_one_line() -> None:
    env = {**GOOD, "GOOGLE_API_KEY": "replace-me", "LIVEKIT_URL": "  "}
    del env["LIVEKIT_API_SECRET"]

    assert missing_settings(env) == [
        "GOOGLE_API_KEY",
        "LIVEKIT_URL",
        "LIVEKIT_API_SECRET",
    ]
    with pytest.raises(SystemExit) as stopped:
        require_settings(env)

    message = str(stopped.value)
    assert "\n" not in message
    assert "GOOGLE_API_KEY" in message
    assert "LIVEKIT_API_KEY" not in message
