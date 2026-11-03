"""Render one support sentence in each curated voice, to pick one by ear.

    uv run --env-file ../../.env python -m kb_agent.voices --out .voice-samples

It uses the Gemini speech model with the same prebuilt voices the live agent
speaks with, so a voice here is the voice in a session. The prosody of the live
model differs a little. Git ignores .voice-samples.
"""

import argparse
import asyncio
import os
import sys
import wave
from collections.abc import Awaitable, Callable
from pathlib import Path

from google.genai import Client, types

from kb_agent.config import missing_settings

TTS_MODEL = "gemini-3.8-flash-tts"
SAMPLE_RATE = 24_000
# Voice, then the trait the speech generation docs give it.
# The API validates product voices against the same names. A test fails on drift.
VOICES = {
    "Sulafat": "warm",
    "Achird": "friendly",
    "Puck": "upbeat",
    "Aoede": "breezy",
    "Sadachbia": "lively",
    "Vindemiatrix": "gentle",
}
SENTENCE = (
    "Hi, I'm Shawn. That error sounds frustrating, but we can sort it out. "
    "First, open the billing page and I'll point at the button you need."
)
Render = Callable[[str], Awaitable[bytes]]


def gemini_render() -> Render:
    client = Client()

    async def render(voice: str) -> bytes:
        reply = await client.aio.models.generate_content(
            model=TTS_MODEL,
            contents=f"Say this warmly and naturally: {SENTENCE}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice
                        )
                    )
                ),
            ),
        )
        for part in reply.parts or []:
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data
        raise RuntimeError(f"no audio came back for {voice}")

    return render


async def write_samples(out: Path, render: Render) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for voice in VOICES:
        path = out / f"{voice}.wav"
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(await render(voice))
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kb_agent.voices")
    parser.add_argument("--out", type=Path, default=Path(".voice-samples"))
    args = parser.parse_args(argv)
    if missing_settings(os.environ, ("GOOGLE_API_KEY",)):
        print("skipped: GOOGLE_API_KEY is not set")
        return 0
    for path in asyncio.run(write_samples(args.out, gemini_render())):
        print(f"{path.stem} ({VOICES[path.stem]}): {path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
