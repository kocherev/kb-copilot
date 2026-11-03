import pytest
from kb_desktop.actions import Cursor, Display
from kb_desktop.cursor import (
    GLIDE_SECONDS,
    LINGER_SECONDS,
    RIPPLE_SECONDS,
    CursorTrack,
)

SCREEN = Display(width=1000, height=500, scale=2.0)


def command(state: str, x: int = 500, y: int = 500, label: str = "Save") -> Cursor:
    return Cursor.model_validate(
        {"state": state, "x": x, "y": y, "name": "Shawn", "label": label}
    )


def test_it_is_hidden_until_the_agent_sends_a_state() -> None:
    assert not CursorTrack().frame(0).visible


def test_the_first_state_appears_in_place_with_the_name_and_label() -> None:
    track = CursorTrack()
    track.show(command("about-to-click", 200, 400), SCREEN, now=10)

    frame = track.frame(10)

    assert frame.visible
    assert (frame.x, frame.y) == (200, 200)
    assert (frame.state, frame.name, frame.label) == ("about-to-click", "Shawn", "Save")
    assert frame.ring > 0


def test_a_new_target_glides_from_the_last_spot_and_lands_on_it() -> None:
    track = CursorTrack()
    track.show(command("thinking", 0, 0), SCREEN, now=0)
    track.show(command("about-to-click", 500, 500), SCREEN, now=1)

    midway = track.frame(1 + GLIDE_SECONDS / 2)
    landed = track.frame(1 + GLIDE_SECONDS)

    assert 0 < midway.x < 500 and 0 < midway.y < 250
    assert (landed.x, landed.y) == (500, 250)


def test_a_click_ripples_once_then_hides_on_its_own() -> None:
    track = CursorTrack()
    track.show(command("clicking"), SCREEN, now=0)

    start, later = track.frame(0), track.frame(RIPPLE_SECONDS * 0.9)

    assert later.ring > start.ring and later.ring_alpha < start.ring_alpha
    assert track.frame(RIPPLE_SECONDS).ring == 0
    assert track.frame(RIPPLE_SECONDS).visible
    assert not track.frame(LINGER_SECONDS["clicking"]).visible


@pytest.mark.parametrize("state", ["thinking", "about-to-click"])
def test_a_waiting_state_stays_until_its_linger_runs_out(state: str) -> None:
    track = CursorTrack()
    track.show(command(state), SCREEN, now=0)

    assert track.frame(LINGER_SECONDS[state] - 0.01).visible
    assert not track.frame(LINGER_SECONDS[state]).visible


def test_hidden_hides_at_once_and_the_next_state_does_not_glide_from_there() -> None:
    track = CursorTrack()
    track.show(command("about-to-click", 0, 0), SCREEN, now=0)
    track.show(command("hidden", 0, 0), SCREEN, now=1)
    assert not track.frame(1).visible

    track.show(command("thinking", 800, 800), SCREEN, now=2)

    assert (track.frame(2).x, track.frame(2).y) == (800, 400)


def test_a_new_state_restarts_the_linger() -> None:
    track = CursorTrack()
    track.show(command("clicking"), SCREEN, now=0)
    track.show(command("thinking"), SCREEN, now=1)

    assert track.frame(1 + LINGER_SECONDS["clicking"]).visible
