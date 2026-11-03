import json

import pytest
from kb_desktop.actions import (
    Action,
    Click,
    Cursor,
    Display,
    InvalidRequest,
    Key,
    Screenshot,
    Scroll,
    TypeText,
    fit,
    handle,
    parse,
)

RETINA = Display(width=1512, height=982, scale=2.0)


def run(method: str, payload: str, display: Display = RETINA) -> list[Action]:
    done: list[Action] = []
    handle(method, payload, display, lambda action, shown: done.append(action))
    return done


def run_reply(method: str, payload: str) -> str:
    return handle(method, payload, RETINA, lambda action, display: None)


@pytest.mark.parametrize(
    ("x", "y", "point"),
    [
        (0, 0, (0, 0)),
        (999, 0, (1510, 0)),
        (0, 999, (0, 981)),
        (999, 999, (1510, 981)),
        (500, 500, (756, 491)),
    ],
)
def test_the_grid_maps_to_logical_points_not_pixels(
    x: int, y: int, point: tuple[int, int]
) -> None:
    assert Click(x=x, y=y).at(RETINA) == point
    # The same grid on a screen that is not scaled lands on its own width.
    assert Scroll(x=x, y=y).at(Display(width=1000, height=1000, scale=1.0)) == (x, y)


def test_a_click_reaches_the_executor_with_the_display_to_map_it() -> None:
    seen: list[tuple[Action, Display]] = []

    handle(
        "desktop.click",
        '{"x": 500, "y": 999, "button": "right"}',
        RETINA,
        lambda action, display: seen.append((action, display)),
    )

    assert seen == [(Click(x=500, y=999, button="right", double=False), RETINA)]
    assert Click(x=500, y=999).at(RETINA) == (756, 981)


def test_a_scroll_reaches_the_executor() -> None:
    assert run("desktop.scroll", '{"x": 0, "y": 500, "dy": 3}') == [
        Scroll(x=0, y=500, dy=3, dx=0)
    ]


def test_info_reports_the_display_and_does_nothing() -> None:
    done: list[Action] = []

    reply = handle(
        "desktop.info", "", RETINA, lambda action, display: done.append(action)
    )

    assert json.loads(reply) == {"width": 1512, "height": 982, "scale": 2.0}
    assert done == []


def test_type_and_key_pass_through() -> None:
    [typed] = run("desktop.type", json.dumps({"text": "é" * 500}))
    [pressed] = run("desktop.key", '{"keys": ["cmd", "shift", "t"]}')

    assert typed == TypeText(text="é" * 500)
    assert pressed == Key(keys=["cmd", "shift", "t"])
    assert json.loads(run_reply("desktop.key", '{"keys": ["f5"]}')) == {"ok": True}


@pytest.mark.parametrize(
    ("method", "payload", "message"),
    [
        ("desktop.click", '{"x": 1000, "y": 0}', "x: "),
        ("desktop.click", '{"x": -1, "y": 0}', "x: "),
        ("desktop.click", '{"x": 1.5, "y": 0}', "x: "),
        ("desktop.click", '{"x": "5", "y": 0}', "x: "),
        ("desktop.click", '{"x": 5}', "y: Field required"),
        ("desktop.click", '{"x": 5, "y": 5, "button": "middle"}', "button: "),
        ("desktop.click", '{"x": 5, "y": 5, "force": true}', "force: "),
        ("desktop.click", "not json", "payload: "),
        ("desktop.click", "[1, 2]", "payload: "),
        ("desktop.type", '{"text": ""}', "text: "),
        ("desktop.type", json.dumps({"text": "a" * 501}), "text: "),
        ("desktop.key", '{"keys": []}', "keys: "),
        ("desktop.key", '{"keys": ["cmd", "banana"]}', r"unknown keys \['banana'\]"),
        ("desktop.key", '{"keys": ["T"]}', r"unknown keys \['T'\]"),
        ("desktop.key", '{"keys": ["cmd"]}', "exactly one other key"),
        ("desktop.key", '{"keys": ["a", "b"]}', "exactly one other key"),
        ("desktop.key", '{"keys": ["cmd", "cmd", "t"]}', "exactly one other key"),
        (
            "desktop.key",
            '{"keys": ["cmd", "ctrl", "alt", "shift", "t", "a"]}',
            "keys: ",
        ),
        ("desktop.scroll", '{"x": 0, "y": 0, "dy": 51}', "dy: "),
        ("desktop.scroll", '{"x": 0, "y": 0, "dx": -51}', "dx: "),
        ("desktop.info", '{"x": 1}', "x: "),
    ],
)
def test_bad_payloads_are_rejected_before_anything_runs(
    method: str, payload: str, message: str
) -> None:
    done: list[Action] = []

    with pytest.raises(InvalidRequest, match=message):
        handle(method, payload, RETINA, lambda action, display: done.append(action))

    assert done == []


@pytest.mark.parametrize(
    ("display", "size"),
    [
        ((1512, 982), (1386, 900)),
        ((3840, 2160), (1440, 810)),
        ((1280, 720), (1280, 720)),
        ((1440, 900), (1440, 900)),
    ],
)
def test_a_screenshot_fits_the_computer_use_box_and_never_grows(
    display: tuple[int, int], size: tuple[int, int]
) -> None:
    assert fit(*display) == size


@pytest.mark.parametrize(
    ("model", "payload", "message"),
    [
        (Screenshot, '{"stream_id": ""}', "stream_id: "),
        (Screenshot, json.dumps({"stream_id": "s" * 65}), "stream_id: "),
        (Cursor, '{"state": "dancing", "x": 1, "y": 1, "name": "S"}', "state: "),
        (Cursor, '{"state": "clicking", "x": 1000, "y": 1, "name": "S"}', "x: "),
        (Cursor, '{"state": "clicking", "x": 1, "y": 1, "name": ""}', "name: "),
        (
            Cursor,
            json.dumps(
                {"state": "hidden", "x": 1, "y": 1, "name": "S", "label": "l" * 81}
            ),
            "label: ",
        ),
    ],
)
def test_screenshot_and_cursor_payloads_are_checked(
    model: type[Screenshot | Cursor], payload: str, message: str
) -> None:
    with pytest.raises(InvalidRequest, match=message):
        parse(model, payload)
