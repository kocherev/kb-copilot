import json
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from kb_agent.product import instructions_for, product_id_from_metadata
from kb_agent.voice import (
    is_screen_share_video,
    model_provider,
    resolve_realtime_model,
    session_room_options,
    voice_attempts,
)
from kb_agent.worker import AGENT_NAME
from livekit import rtc

PRODUCT_ID = "11111111-1111-4111-8111-111111111111"
PRODUCT = {
    "id": PRODUCT_ID,
    "name": "Acme",
    "description": "Acme helps customers reset passwords.",
    "tone": "calm and brief",
    "refusal_rules": "Do not invent a refund policy.",
}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == f"/products/{PRODUCT_ID}":
            body = json.dumps(PRODUCT).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, message: str, *args: object) -> None:
        return


@pytest.fixture
def api_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host = str(server.server_address[0])
    port = int(server.server_address[1])
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()


def test_dispatch_metadata_selects_the_product_prompt(api_url: str) -> None:
    metadata = json.dumps({"product_id": PRODUCT_ID})

    instructions = instructions_for(metadata, api_url)

    assert product_id_from_metadata(metadata) == PRODUCT_ID
    assert "You are the support agent for Acme." in instructions
    assert "Tone: calm and brief" in instructions
    assert "Do not invent a refund policy." in instructions
    assert AGENT_NAME == "kb-support"
    with pytest.raises(ValueError, match="product_id is required"):
        product_id_from_metadata("{}")
    with pytest.raises(ValueError, match="JSON"):
        product_id_from_metadata("not-json")
    with pytest.raises(ValueError, match="404"):
        instructions_for(
            json.dumps({"product_id": "00000000-0000-0000-0000-000000000000"}),
            api_url,
        )


def test_room_options_enable_screen_share_video() -> None:
    options = session_room_options()

    assert options.get_video_input_options() is not None
    assert options.get_audio_input_options() is not None
    assert options.get_audio_output_options() is not None
    assert is_screen_share_video(
        rtc.TrackSource.SOURCE_SCREENSHARE,
        rtc.TrackKind.KIND_VIDEO,
    )
    assert not is_screen_share_video(
        rtc.TrackSource.SOURCE_CAMERA,
        rtc.TrackKind.KIND_VIDEO,
    )
    assert not is_screen_share_video(
        rtc.TrackSource.SOURCE_SCREENSHARE,
        rtc.TrackKind.KIND_AUDIO,
    )


def test_model_provider_follows_the_livekit_host() -> None:
    assert model_provider("wss://example.livekit.cloud") == "livekit"
    assert model_provider("wss://livekit.cloud") == "livekit"
    assert model_provider("wss://Acme.LiveKit.Cloud") == "livekit"
    assert model_provider("ws://localhost:7880") == "openai"
    assert model_provider("ws://livekit:7880") == "openai"
    assert model_provider("wss://evil.livekit.cloud.example") == "openai"


def test_self_hosted_voice_uses_openai_and_cloud_uses_inference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    # Inference reads these at construction. CI does not provide them.
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret-placeholder-32bytes!")
    from kb_agent.voice import build_voice

    local = build_voice("ws://livekit:7880")
    cloud = build_voice("wss://example.livekit.cloud")
    fallback = build_voice(
        "wss://example.livekit.cloud",
        realtime_model="google/gemini-3.8-live",
    )

    assert "openai" in local.stt.label
    assert "openai" in local.llm.label
    assert "openai" in local.tts.label
    assert local.realtime_model is None
    assert local.provider == "openai"
    assert local.stt.label != cloud.stt.label
    assert "inference" in cloud.stt.label
    assert "inference" in cloud.llm.label
    assert "inference" in cloud.tts.label
    assert cloud.provider == "livekit"
    assert cloud.realtime_model == "google/gemini-3.8-live-extended-thinking"
    assert cloud.llm.model == "google/gemini-3.8-live-extended-thinking"
    assert cloud.voice == "Puck"
    assert cloud.reasoning_effort == "low"
    assert cloud.video_speaking_fps == 1.0
    assert cloud.video_silent_fps == 0.3
    assert fallback.realtime_model == "google/gemini-3.8-live"
    assert fallback.reasoning_effort is None
    assert voice_attempts("wss://example.livekit.cloud") == (
        "google/gemini-3.8-live-extended-thinking",
        "google/gemini-3.8-live",
        "google/gemini-live",
    )
    assert voice_attempts("ws://localhost:7880") == (None,)
    assert resolve_realtime_model(None) == "google/gemini-3.8-live-extended-thinking"
    with pytest.raises(ValueError, match="unsupported realtime model"):
        resolve_realtime_model("google/gemma-4-31b-it")


def test_cloud_latency_logs_read_session_metrics(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret-placeholder-32bytes!")
    from kb_agent.voice import attach_latency_logs, build_voice
    from livekit.agents import MetricsCollectedEvent
    from livekit.agents.metrics import RealtimeModelMetrics

    cloud = build_voice("wss://example.livekit.cloud")
    attach_latency_logs(cloud)
    cloud.session.emit(
        "metrics_collected",
        MetricsCollectedEvent(
            metrics=RealtimeModelMetrics(
                label="realtime",
                request_id="rt-1",
                timestamp=1.0,
                duration=0.4,
                ttft=0.2,
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
                input_token_details=RealtimeModelMetrics.InputTokenDetails(
                    image_tokens=30,
                    audio_tokens=70,
                ),
                output_token_details=RealtimeModelMetrics.OutputTokenDetails(
                    audio_tokens=20,
                ),
            )
        ),
    )

    logged = capsys.readouterr().out
    assert '"image_tokens": 30' in logged
    assert '"segment": "realtime"' in logged
