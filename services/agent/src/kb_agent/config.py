from collections.abc import Mapping

PLACEHOLDERS = {"", "replace-me"}
REQUIRED = ("GOOGLE_API_KEY", "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")


def missing_settings(
    env: Mapping[str, str], names: tuple[str, ...] = REQUIRED
) -> list[str]:
    return [name for name in names if env.get(name, "").strip() in PLACEHOLDERS]


def require_settings(env: Mapping[str, str], names: tuple[str, ...] = REQUIRED) -> None:
    """Exit with one readable line instead of retrying a worker that cannot work."""
    missing = missing_settings(env, names)
    if missing:
        raise SystemExit(
            f"kb-agent cannot start: set {', '.join(missing)} to a real value."
        )
