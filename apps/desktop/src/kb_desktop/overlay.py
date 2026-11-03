# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
# pyright: reportIncompatibleMethodOverride=false
# pyobjc is installed on macOS only and loads its names at run time.
"""Draw the agent cursor on the real screen. macOS only.

A small borderless window that ignores the mouse floats above everything and
follows the cursor frame by frame. The asyncio loop runs on the main thread and
pumps AppKit between frames, so there is no second thread to coordinate.
"""

import asyncio
import time
from collections.abc import Callable

import AppKit
import objc
import Quartz

from kb_desktop.actions import Cursor, Display
from kb_desktop.cursor import HIDDEN, CursorTrack, Frame

FPS = 60
# The window is centred on the arrow tip so the tag can sit on either side.
WIDTH, HEIGHT = 560, 140
TIP = (WIDTH / 2, 44)
ARROW = 22
TAG_FONT = 12
ACCENT = AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(0.15, 0.39, 0.92, 1)
WHITE = AppKit.NSColor.whiteColor()


def arrow_path(scale: float, dx: float, dy: float) -> AppKit.NSBezierPath:
    # The same arrow as the web cursor, with its tip at (5, 2) of a 24 unit box.
    path = AppKit.NSBezierPath.bezierPath()
    points = [(5, 2), (19, 9), (13, 10.7), (11, 18)]
    path.moveToPoint_(
        ((points[0][0] - 5) * scale + dx, (points[0][1] - 2) * scale + dy)
    )
    for x, y in points[1:]:
        path.lineToPoint_(((x - 5) * scale + dx, (y - 2) * scale + dy))
    path.closePath()
    path.setLineJoinStyle_(AppKit.NSLineJoinStyleRound)
    return path


class CursorView(AppKit.NSView):
    def initWithFrame_(self, rect):
        self = objc.super(CursorView, self).initWithFrame_(rect)
        self.shown = HIDDEN
        self.flip = False
        return self

    def isFlipped(self) -> bool:
        return True

    def drawRect_(self, rect) -> None:
        frame = self.shown
        if not frame.visible:
            return
        tx, ty = TIP
        if frame.ring > 0:
            ACCENT.colorWithAlphaComponent_(frame.ring_alpha).setStroke()
            ring = AppKit.NSBezierPath.bezierPathWithOvalInRect_(
                ((tx - frame.ring, ty - frame.ring), (frame.ring * 2, frame.ring * 2))
            )
            ring.setLineWidth_(3)
            ring.stroke()
        path = arrow_path(ARROW / 24, tx, ty)
        WHITE.setStroke()
        path.setLineWidth_(5)
        path.stroke()
        ACCENT.set()
        path.setLineWidth_(2.5)
        path.stroke()
        path.fill()
        self.draw_tag(frame, tx, ty)

    def draw_tag(self, frame: Frame, tx: float, ty: float) -> None:
        title = frame.name + (" …" if frame.state == "thinking" else "")
        lines = [title, frame.label] if frame.label else [title]
        fonts = [
            AppKit.NSFont.boldSystemFontOfSize_(TAG_FONT),
            AppKit.NSFont.systemFontOfSize_(TAG_FONT),
        ]
        texts = [
            AppKit.NSAttributedString.alloc().initWithString_attributes_(
                line,
                {
                    AppKit.NSFontAttributeName: font,
                    AppKit.NSForegroundColorAttributeName: WHITE,
                },
            )
            for line, font in zip(lines, fonts, strict=False)
        ]
        width = max(text.size().width for text in texts) + 16
        height = sum(text.size().height for text in texts) + 8
        left = tx - width - 6 if self.flip else tx + ARROW * 0.62
        top = ty + ARROW * 0.72
        AppKit.NSColor.colorWithWhite_alpha_(0, 0.25).setFill()
        AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            ((left, top + 1), (width, height)), 8, 8
        ).fill()
        ACCENT.setFill()
        AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            ((left, top), (width, height)), 8, 8
        ).fill()
        y = top + 4
        for text in texts:
            text.drawAtPoint_((left + 8, y))
            y += text.size().height


class Overlay:
    def __init__(self) -> None:
        self.app = AppKit.NSApplication.sharedApplication()
        # No Dock icon and no menu bar: the helper stays a terminal program.
        self.app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
        self.app.finishLaunching()
        main = AppKit.NSScreen.screens()[0].frame()
        self.screen = (main.size.width, main.size.height)
        window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (WIDTH, HEIGHT)),
            AppKit.NSWindowStyleMaskBorderless,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        window.setOpaque_(False)
        window.setBackgroundColor_(AppKit.NSColor.clearColor())
        window.setHasShadow_(False)
        window.setIgnoresMouseEvents_(True)
        window.setLevel_(Quartz.CGWindowLevelForKey(Quartz.kCGOverlayWindowLevelKey))
        window.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorStationary
            | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
            | AppKit.NSWindowCollectionBehaviorIgnoresCycle
        )
        # Keeps it out of screen shares that honour the flag, so the browser
        # preview does not show a second cursor.
        window.setSharingType_(AppKit.NSWindowSharingNone)
        self.view = CursorView.alloc().initWithFrame_(((0, 0), (WIDTH, HEIGHT)))
        window.setContentView_(self.view)
        self.window = window

    def draw(self, frame: Frame) -> None:
        if frame == self.view.shown:
            return
        self.view.shown = frame
        if not frame.visible:
            self.window.orderOut_(None)
            return
        width, height = self.screen
        self.view.flip = frame.x > width - WIDTH / 2
        # AppKit counts y up from the bottom of the main screen.
        self.window.setFrameOrigin_(
            (frame.x - TIP[0], height - frame.y - (HEIGHT - TIP[1]))
        )
        self.view.setNeedsDisplay_(True)
        self.window.orderFrontRegardless()

    def pump(self) -> None:
        while True:
            event = self.app.nextEventMatchingMask_untilDate_inMode_dequeue_(
                AppKit.NSEventMaskAny,
                AppKit.NSDate.distantPast(),
                AppKit.NSDefaultRunLoopMode,
                True,
            )
            if event is None:
                break
            self.app.sendEvent_(event)
        self.window.displayIfNeeded()

    async def animate(self, track: CursorTrack) -> None:
        while True:
            self.draw(track.frame(time.monotonic()))
            self.pump()
            await asyncio.sleep(1 / FPS)


# The loop holds tasks weakly, so keep the animation alive here.
_running: set[asyncio.Task[None]] = set()


def start() -> Callable[[Cursor, Display], None]:
    """Open the overlay and return what the desktop.cursor method calls.

    Call it from the running asyncio loop on the main thread.
    """
    overlay = Overlay()
    track = CursorTrack()
    task = asyncio.get_running_loop().create_task(overlay.animate(track))
    _running.add(task)

    def show(command: Cursor, display: Display) -> None:
        track.show(command, display, time.monotonic())

    return show
