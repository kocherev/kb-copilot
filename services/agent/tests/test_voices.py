import asyncio
import json
import wave
from pathlib import Path

import pytest
from kb_agent import voices

ROOT = Path(__file__).resolve().parents[3]


def test_it_skips_cleanly_without_a_key(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    assert voices.main(["--out", str(tmp_path / "samples")]) == 0
    assert "skipped: GOOGLE_API_KEY is not set" in capsys.readouterr().out
    assert not (tmp_path / "samples").exists()


def test_each_voice_becomes_a_playable_wav(tmp_path: Path) -> None:
    async def render(voice: str) -> bytes:
        return voice.encode() * 100

    paths = asyncio.run(voices.write_samples(tmp_path, render))

    assert [path.name for path in paths] == [f"{name}.wav" for name in voices.VOICES]
    with wave.open(str(paths[0])) as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (
            1,
            2,
            24_000,
        )
        assert wav.readframes(wav.getnframes()) == b"Sulafat" * 100


def test_the_voices_are_the_ones_the_api_accepts() -> None:
    spec = json.loads((ROOT / "apps/web/openapi.json").read_text())
    accepted = spec["components"]["schemas"]["ProductWrite"]["properties"]["voice"]

    assert list(voices.VOICES) == accepted["enum"]
    assert accepted["default"] == next(iter(voices.VOICES))
