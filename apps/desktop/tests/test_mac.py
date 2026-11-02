"""macOS-only checks that read the screen and post no events."""

import pytest
from kb_desktop.actions import MODIFIERS

mac = pytest.importorskip("kb_desktop.mac")


def test_every_modifier_has_a_quartz_flag() -> None:
    assert set(mac.FLAGS) == set(MODIFIERS)
    assert len(set(mac.FLAGS.values())) == len(MODIFIERS)


def test_the_main_display_is_in_logical_points() -> None:
    display = mac.main_display()

    assert display.width > 0 and display.height > 0
    assert display.scale >= 1
