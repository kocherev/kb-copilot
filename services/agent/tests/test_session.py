import asyncio

import pytest
from kb_agent import session as live
from livekit.agents import AgentSession


async def _build() -> AgentSession:
    return live.build_session()


def test_the_model_is_gemini_live_with_low_thinking_and_medium_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("KB_VOICE", "Kore")

    built = asyncio.run(_build())

    model = built.llm
    assert model.model == "gemini-3.8-live-extended-thinking"  # type: ignore[union-attr]
    opts = model._opts  # type: ignore[union-attr]
    assert opts.voice == "Kore"
    assert opts.thinking_config.thinking_level == "LOW"
    assert opts.media_resolution == "MEDIA_RESOLUTION_MEDIUM"
    sampler = built._video_sampler
    assert (sampler.speaking_fps, sampler.silent_fps) == (1.0, 0.3)  # type: ignore[union-attr]


def test_the_default_voice_is_puck(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("KB_VOICE", raising=False)

    assert asyncio.run(_build()).llm._opts.voice == "Puck"  # type: ignore[union-attr]


def test_the_session_subscribes_to_screen_video() -> None:
    options = live.room_options()

    assert options.get_video_input_options() is not None
    assert options.get_audio_input_options() is not None


def test_the_session_limit_defaults_and_rejects_nonsense() -> None:
    assert live.max_session_seconds(None) == 600
    assert live.max_session_seconds("") == 600
    assert live.max_session_seconds("90") == 90
    with pytest.raises(ValueError):
        live.max_session_seconds("0")
    with pytest.raises(ValueError):
        live.max_session_seconds("soon")


class _Session:
    def __init__(self, fail: bool = False) -> None:
        self.said: list[str] = []
        self.fail = fail

    def generate_reply(self, *, instructions: str) -> asyncio.Future[None]:
        self.said.append(instructions)
        done: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        if self.fail:
            done.set_exception(RuntimeError("model gone"))
        else:
            done.set_result(None)
        return done


def _enforce(session: _Session, seconds: float) -> list[str]:
    events: list[str] = []

    async def run() -> None:
        await live.enforce_time_limit(
            session,  # type: ignore[arg-type]
            seconds,
            lambda: events.append("closed"),
        )

    asyncio.run(run())
    return events


def test_the_limit_says_goodbye_then_closes() -> None:
    session = _Session()

    assert _enforce(session, 0.01) == ["closed"]
    assert session.said == [live.GOODBYE]


def test_the_limit_closes_even_when_the_goodbye_fails() -> None:
    assert _enforce(_Session(fail=True), 0.01) == ["closed"]


def test_nothing_happens_before_the_limit() -> None:
    session = _Session()

    async def run() -> None:
        task = asyncio.create_task(
            live.enforce_time_limit(session, 60, lambda: None)  # type: ignore[arg-type]
        )
        await asyncio.sleep(0.01)
        task.cancel()

    asyncio.run(run())

    assert session.said == []
