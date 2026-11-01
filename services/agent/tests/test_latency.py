import json

from kb_agent.latency import component_latency, log_json, turn_latency
from livekit.agents.metrics import (
    LLMMetrics,
    RealtimeModelMetrics,
    STTMetrics,
    TTSMetrics,
    VADMetrics,
)


def test_component_latency_logs_stt_llm_and_tts(capsys) -> None:
    stt = STTMetrics(
        label="stt",
        request_id="stt-1",
        timestamp=1.0,
        duration=0.12,
        audio_duration=0.8,
        streamed=False,
    )
    llm = LLMMetrics(
        label="llm",
        request_id="llm-1",
        timestamp=2.0,
        duration=0.4,
        ttft=0.18,
        cancelled=False,
        completion_tokens=12,
        prompt_tokens=40,
        prompt_cached_tokens=0,
        total_tokens=52,
        tokens_per_second=30.0,
        speech_id="speech-1",
    )
    tts = TTSMetrics(
        label="tts",
        request_id="tts-1",
        timestamp=3.0,
        ttfb=0.09,
        duration=0.5,
        audio_duration=1.2,
        cancelled=False,
        characters_count=24,
        streamed=True,
        speech_id="speech-1",
    )

    for metric in (stt, llm, tts):
        record = component_latency(metric)
        assert record is not None
        log_json(record)

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [line["segment"] for line in lines] == ["stt", "llm", "tts"]
    assert lines[0]["kind"] == "component"
    assert lines[0]["duration_ms"] == 120
    assert lines[0]["audio_duration_ms"] == 800
    assert lines[1]["ttft_ms"] == 180
    assert lines[1]["speech_id"] == "speech-1"
    assert lines[2]["ttfb_ms"] == 90
    assert lines[2]["speech_id"] == "speech-1"
    assert (
        component_latency(
            VADMetrics(
                label="vad",
                timestamp=1.0,
                idle_time=0.0,
                inference_duration_total=0.01,
                inference_count=1,
            )
        )
        is None
    )


def test_component_latency_logs_realtime_image_tokens() -> None:
    metric = RealtimeModelMetrics(
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
        output_token_details=RealtimeModelMetrics.OutputTokenDetails(audio_tokens=20),
    )

    record = component_latency(metric)

    assert record == {
        "kind": "component",
        "segment": "realtime",
        "duration_ms": 400,
        "input_tokens": 100,
        "output_tokens": 20,
        "image_tokens": 30,
        "ttft_ms": 200,
    }


def test_turn_latency_logs_stt_llm_and_tts_segments(capsys) -> None:
    user = turn_latency(
        "user",
        {"transcription_delay": 0.15, "end_of_turn_delay": 0.04},
    )
    assistant = turn_latency(
        "assistant",
        {"llm_node_ttft": 0.18, "tts_node_ttfb": 0.09, "e2e_latency": 0.4},
    )
    assert user is not None
    assert assistant is not None
    log_json(user)
    log_json(assistant)

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines[0] == {
        "end_of_turn_delay_ms": 40,
        "kind": "turn",
        "role": "user",
        "transcription_delay_ms": 150,
    }
    assert lines[1] == {
        "e2e_latency_ms": 400,
        "kind": "turn",
        "llm_ttft_ms": 180,
        "role": "assistant",
        "tts_ttfb_ms": 90,
    }
    partial = turn_latency("assistant", {"llm_node_ttft": 0.2})
    assert partial == {"kind": "turn", "role": "assistant", "llm_ttft_ms": 200}
    assert turn_latency("system", {"llm_node_ttft": 0.2}) is None
