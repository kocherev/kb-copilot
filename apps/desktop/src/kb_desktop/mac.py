# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
# pyobjc is installed on macOS only and loads its names at run time.
"""Post mouse and keyboard events with Quartz. The only macOS module."""

import ctypes
import time

import Quartz

from kb_desktop.actions import (
    KEYCODES,
    MODIFIERS,
    Action,
    Click,
    Display,
    Key,
    Scroll,
    TypeText,
)

FLAGS = {
    "cmd": Quartz.kCGEventFlagMaskCommand,
    "ctrl": Quartz.kCGEventFlagMaskControl,
    "alt": Quartz.kCGEventFlagMaskAlternate,
    "shift": Quartz.kCGEventFlagMaskShift,
}
KEY_DELAY = 0.005
HOVER_DELAY = 0.05


def accessibility_trusted() -> bool:
    lib = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
    )
    lib.AXIsProcessTrusted.restype = ctypes.c_bool
    return lib.AXIsProcessTrusted()


def main_display() -> Display:
    display = Quartz.CGMainDisplayID()
    size = Quartz.CGDisplayBounds(display).size
    return Display(
        width=int(size.width),
        height=int(size.height),
        scale=Quartz.CGDisplayPixelsWide(display) / size.width,
    )


def post(event: object) -> None:
    if event is None:
        raise RuntimeError("macOS refused to create the input event")
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def mouse(kind: int, x: int, y: int, button: int, click_state: int = 1) -> None:
    event = Quartz.CGEventCreateMouseEvent(None, kind, (x, y), button)
    Quartz.CGEventSetIntegerValueField(
        event, Quartz.kCGMouseEventClickState, click_state
    )
    post(event)


def key_pair(code: int, flags: int = 0, text: str | None = None) -> None:
    for down in (True, False):
        event = Quartz.CGEventCreateKeyboardEvent(None, code, down)
        if text is not None:
            Quartz.CGEventKeyboardSetUnicodeString(
                event, len(text.encode("utf-16-le")) // 2, text
            )
        Quartz.CGEventSetFlags(event, flags)
        post(event)


def execute(action: Action, display: Display) -> None:
    match action:
        case Click():
            x, y = action.at(display)
            right = action.button == "right"
            mouse(Quartz.kCGEventMouseMoved, x, y, Quartz.kCGMouseButtonLeft)
            time.sleep(HOVER_DELAY)
            down = (
                Quartz.kCGEventRightMouseDown if right else Quartz.kCGEventLeftMouseDown
            )
            up = Quartz.kCGEventRightMouseUp if right else Quartz.kCGEventLeftMouseUp
            button = Quartz.kCGMouseButtonRight if right else Quartz.kCGMouseButtonLeft
            for state in range(1, 3 if action.double else 2):
                mouse(down, x, y, button, state)
                mouse(up, x, y, button, state)
        case TypeText():
            for char in action.text:
                key_pair(0, text=char)
                time.sleep(KEY_DELAY)
        case Key():
            # Each modifier is a distinct bit and a key repeats at most once.
            flags = sum(FLAGS.get(key, 0) for key in action.keys)
            [plain] = [key for key in action.keys if key not in MODIFIERS]
            key_pair(KEYCODES[plain], flags)
        case Scroll():
            x, y = action.at(display)
            mouse(Quartz.kCGEventMouseMoved, x, y, Quartz.kCGMouseButtonLeft)
            time.sleep(HOVER_DELAY)
            # Quartz counts positive vertical lines as up.
            post(
                Quartz.CGEventCreateScrollWheelEvent(
                    None, Quartz.kCGScrollEventUnitLine, 2, -action.dy, action.dx
                )
            )
