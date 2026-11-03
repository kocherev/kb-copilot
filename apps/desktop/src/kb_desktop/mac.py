# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
# pyobjc is installed on macOS only and loads its names at run time.
"""Capture the screen and post mouse and keyboard events. macOS only, like
overlay.py."""

import ctypes
import os
import threading
import time

import Quartz
import ScreenCaptureKit as SCK
from Foundation import NSMutableData

from kb_desktop.actions import (
    KEYCODES,
    MODIFIERS,
    Action,
    Click,
    Display,
    Key,
    Scroll,
    TypeText,
    fit,
)

FLAGS = {
    "cmd": Quartz.kCGEventFlagMaskCommand,
    "ctrl": Quartz.kCGEventFlagMaskControl,
    "alt": Quartz.kCGEventFlagMaskAlternate,
    "shift": Quartz.kCGEventFlagMaskShift,
}
KEY_DELAY = 0.005
HOVER_DELAY = 0.05
CAPTURE_TIMEOUT = 10


def accessibility_trusted() -> bool:
    lib = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
    )
    lib.AXIsProcessTrusted.restype = ctypes.c_bool
    return lib.AXIsProcessTrusted()


def screen_recording_allowed() -> bool:
    """Asks nothing. CGRequestScreenCaptureAccess is the call that prompts."""
    return Quartz.CGPreflightScreenCaptureAccess()


def ask_for_screen_recording() -> None:
    """Adds this terminal to the Screen Recording list, switched off."""
    Quartz.CGRequestScreenCaptureAccess()


def png(image: object) -> bytes:
    data = NSMutableData.data()
    target = Quartz.CGImageDestinationCreateWithData(data, "public.png", 1, None)
    Quartz.CGImageDestinationAddImage(target, image, None)
    if not Quartz.CGImageDestinationFinalize(target):
        raise RuntimeError("could not encode the screenshot")
    return bytes(data)


def capture(display: Display) -> bytes:
    """The main display as a PNG, scaled down by fit, without this app's windows.

    Blocks until ScreenCaptureKit answers, so call it from a worker thread.
    """
    width, height = fit(display.width, display.height)
    done = threading.Event()
    result: dict[str, object] = {}

    def finish(image: object, error: object) -> None:
        result.update(image=image, error=error)
        done.set()

    def with_content(content: object, error: object) -> None:
        if content is None:
            finish(None, error)
            return
        main = Quartz.CGMainDisplayID()
        screen = next(d for d in content.displays() if d.displayID() == main)
        # The agent cursor overlay is our own window. The model should not see it.
        own = [
            w
            for w in content.windows()
            if w.owningApplication() is not None
            and w.owningApplication().processID() == os.getpid()
        ]
        only = SCK.SCContentFilter.alloc().initWithDisplay_excludingWindows_(
            screen, own
        )
        config = SCK.SCStreamConfiguration.alloc().init()
        config.setWidth_(width)
        config.setHeight_(height)
        config.setShowsCursor_(True)
        SCK.SCScreenshotManager.captureImageWithFilter_configuration_completionHandler_(
            only, config, finish
        )

    SCK.SCShareableContent.getShareableContentWithCompletionHandler_(with_content)
    if not done.wait(CAPTURE_TIMEOUT):
        raise RuntimeError("the screen capture did not answer")
    if result["image"] is None:
        raise RuntimeError(f"the screen capture failed: {result['error']}")
    return png(result["image"])


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
