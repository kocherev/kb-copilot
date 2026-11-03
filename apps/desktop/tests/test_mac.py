"""macOS-only checks. They read the screen size, encode and draw off screen, and
post no events. Nothing here asks macOS for a permission."""

import pytest
from kb_desktop.actions import MODIFIERS, fit
from kb_desktop.cursor import HIDDEN, Frame

mac = pytest.importorskip("kb_desktop.mac")
overlay = pytest.importorskip("kb_desktop.overlay")
Quartz = pytest.importorskip("Quartz")


def test_every_modifier_has_a_quartz_flag() -> None:
    assert set(mac.FLAGS) == set(MODIFIERS)
    assert len(set(mac.FLAGS.values())) == len(MODIFIERS)


def test_the_main_display_is_in_logical_points() -> None:
    display = mac.main_display()

    assert display.width > 0 and display.height > 0
    assert display.scale >= 1


def size_of(png: bytes) -> tuple[int, int]:
    source = Quartz.CGImageSourceCreateWithData(png, None)
    image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)
    return Quartz.CGImageGetWidth(image), Quartz.CGImageGetHeight(image)


def test_a_picture_is_encoded_as_png() -> None:
    context = Quartz.CGBitmapContextCreate(
        None, 64, 40, 8, 0, Quartz.CGColorSpaceCreateDeviceRGB(),
        Quartz.kCGImageAlphaPremultipliedLast,
    )  # fmt: skip
    encoded = mac.png(Quartz.CGBitmapContextCreateImage(context))

    assert encoded.startswith(b"\x89PNG\r\n\x1a\n")
    assert size_of(encoded) == (64, 40)


@pytest.mark.skipif(
    not mac.screen_recording_allowed(), reason="Screen Recording is not granted"
)
def test_the_screen_is_captured_at_the_fitted_size() -> None:
    display = mac.main_display()

    assert size_of(mac.capture(display)) == fit(display.width, display.height)


def alpha_at(frame: Frame, x: float, y: float) -> int:
    view = overlay.CursorView.alloc().initWithFrame_(
        ((0, 0), (overlay.WIDTH, overlay.HEIGHT))
    )
    view.shown = frame
    bitmap = view.bitmapImageRepForCachingDisplayInRect_(view.bounds())
    view.cacheDisplayInRect_toBitmapImageRep_(view.bounds(), bitmap)
    scale = bitmap.pixelsWide() / overlay.WIDTH
    return bitmap.colorAtX_y_(int(x * scale), int(y * scale)).alphaComponent()


def test_the_overlay_draws_the_arrow_at_the_tip_and_nothing_when_hidden() -> None:
    tip_x, tip_y = overlay.TIP
    shown = Frame(visible=True, state="clicking", name="Shawn", label="Save")
    # Just inside the arrow, below and right of its tip.
    inside = (tip_x + 4, tip_y + 6)

    assert alpha_at(shown, *inside) > 0.9
    assert alpha_at(HIDDEN, *inside) == 0
    assert alpha_at(shown, 4, 4) == 0
