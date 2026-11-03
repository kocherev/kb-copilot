from pathlib import Path

import pytest
from kb_agent.selfcheck import load_frame, main

PICTURE = Path(__file__).parent / "fixtures" / "billing-screen.png"


def test_it_skips_cleanly_without_a_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    assert main(["--image", str(PICTURE), "--question", "What is shown?"]) == 0
    assert "skipped: GOOGLE_API_KEY is not set" in capsys.readouterr().out


def test_the_fixture_becomes_a_full_size_rgba_frame() -> None:
    frame = load_frame(PICTURE)

    assert (frame.width, frame.height) == (1280, 720)
    assert len(frame.data) == 1280 * 720 * 4
