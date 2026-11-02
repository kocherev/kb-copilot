"""Validate desktop RPC payloads and hand each action to an executor.

Nothing here touches the operating system, so it runs on any platform.
"""

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

# Gemini Computer Use describes points on a 1000 by 1000 grid, 0 to 999.
GRID = 1000
MODIFIERS = ("cmd", "ctrl", "alt", "shift")
# Virtual key codes of the US keyboard layout. Typed text does not use them.
KEYCODES: dict[str, int] = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8,
    "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25,
    "7": 26, "-": 27, "8": 28, "0": 29, "]": 30, "o": 31, "u": 32, "[": 33,
    "i": 34, "p": 35, "l": 37, "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42,
    ",": 43, "/": 44, "n": 45, "m": 46, ".": 47, "`": 50,
    "enter": 36, "tab": 48, "space": 49, "backspace": 51, "escape": 53,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98,
    "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    "home": 115, "pageup": 116, "delete": 117, "end": 119, "pagedown": 121,
    "left": 123, "right": 124, "down": 125, "up": 126,
}  # fmt: skip


NAMED_KEYS = [key for key in KEYCODES if len(key) > 1]


class InvalidRequest(Exception):
    """The payload is not a valid call of this method."""


@dataclass(frozen=True)
class Display:
    """The main display in logical points. A Retina screen has scale 2."""

    width: int
    height: int
    scale: float


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Info(Strict):
    pass


class Pointer(Strict):
    """A spot on the 0..999 grid."""

    x: int = Field(ge=0, lt=GRID)
    y: int = Field(ge=0, lt=GRID)

    def at(self, display: Display) -> tuple[int, int]:
        """The spot in logical points, which is what Quartz takes on Retina too."""
        return self.x * display.width // GRID, self.y * display.height // GRID


class Click(Pointer):
    button: Literal["left", "right"] = "left"
    double: bool = False


class TypeText(Strict):
    text: str = Field(min_length=1, max_length=500)


class Key(Strict):
    keys: list[str] = Field(min_length=1, max_length=len(MODIFIERS) + 1)

    @field_validator("keys")
    @classmethod
    def _combination(cls, keys: list[str]) -> list[str]:
        unknown = [key for key in keys if key not in KEYCODES and key not in MODIFIERS]
        if unknown:
            raise ValueError(
                f"unknown keys {unknown}; modifiers: {list(MODIFIERS)}; other keys: "
                f"letters, digits, punctuation and {NAMED_KEYS}"
            )
        plain = [key for key in keys if key not in MODIFIERS]
        if len(plain) != 1 or len(set(keys)) != len(keys):
            raise ValueError("give any modifiers plus exactly one other key")
        return keys


class Scroll(Pointer):
    """Positive dy scrolls down and positive dx scrolls right."""

    dy: int = Field(default=0, ge=-50, le=50)
    dx: int = Field(default=0, ge=-50, le=50)


Action = Click | TypeText | Key | Scroll
Executor = Callable[[Action, Display], None]

METHODS: dict[str, type[Info | Action]] = {
    "desktop.info": Info,
    "desktop.click": Click,
    "desktop.type": TypeText,
    "desktop.key": Key,
    "desktop.scroll": Scroll,
}


def describe(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(map(str, item['loc'])) or 'payload'}: "
        f"{item['msg'].removeprefix('Value error, ')}"
        for item in error.errors(include_url=False, include_input=False)
    )


def handle(method: str, payload: str, display: Display, executor: Executor) -> str:
    """Run one RPC call and return its JSON response."""
    try:
        action = METHODS[method].model_validate_json(payload or "{}")
    except ValidationError as exc:
        raise InvalidRequest(describe(exc)) from exc
    if isinstance(action, Info):
        return json.dumps(asdict(display))
    executor(action, display)
    return json.dumps({"ok": True})
