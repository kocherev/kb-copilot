"""Where the on-screen agent cursor is and what it shows, frame by frame.

Plain arithmetic, so it runs anywhere. overlay.py draws each frame on macOS.
"""

import math
from dataclasses import dataclass

from kb_desktop.actions import Cursor, Display

GLIDE_SECONDS = 0.35
RIPPLE_SECONDS = 0.6
PULSE_SECONDS = 1.2
# How long each state stays up without a new command. The agent waits at most
# a minute for an approval, so about-to-click outlasts that.
LINGER_SECONDS = {
    "thinking": 30.0,
    "about-to-click": 90.0,
    "clicking": 1.5,
    "hidden": 0.0,
}


@dataclass(frozen=True)
class Frame:
    """One drawn frame. x and y are the arrow tip in logical points from the
    top left of the main display. ring is a radius around the tip, 0 for none."""

    visible: bool
    x: float = 0
    y: float = 0
    state: str = "hidden"
    name: str = ""
    label: str = ""
    ring: float = 0
    ring_alpha: float = 0


HIDDEN = Frame(visible=False)


def ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


class CursorTrack:
    def __init__(self) -> None:
        self.command: Cursor | None = None
        self.start = (0.0, 0.0)
        self.target = (0.0, 0.0)
        self.since = 0.0

    def show(self, command: Cursor, display: Display, now: float) -> None:
        target = command.at(display)
        # It glides from where it is, and appears in place after it was hidden.
        shown = self.frame(now)
        self.start = (shown.x, shown.y) if shown.visible else target
        self.target = (float(target[0]), float(target[1]))
        self.command = command
        self.since = now

    def frame(self, now: float) -> Frame:
        command = self.command
        elapsed = now - self.since
        if command is None or elapsed >= LINGER_SECONDS[command.state]:
            return HIDDEN
        t = ease_out(min(1.0, elapsed / GLIDE_SECONDS))
        x = self.start[0] + (self.target[0] - self.start[0]) * t
        y = self.start[1] + (self.target[1] - self.start[1]) * t
        ring, alpha = 0.0, 0.0
        if command.state == "about-to-click":
            ring = 16 + 4 * math.sin(elapsed * 2 * math.pi / PULSE_SECONDS)
            alpha = 0.9
        elif command.state == "clicking" and elapsed < RIPPLE_SECONDS:
            spread = elapsed / RIPPLE_SECONDS
            ring, alpha = 6 + 26 * spread, 1 - spread
        return Frame(
            visible=True,
            x=x,
            y=y,
            state=command.state,
            name=command.name,
            label=command.label,
            ring=ring,
            ring_alpha=alpha,
        )
