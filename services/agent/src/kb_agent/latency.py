import json
from collections.abc import Mapping

from livekit.agents.metrics import (
    LLMMetrics,
    RealtimeModelMetrics,
    STTMetrics,
    TTSMetrics,
)

ComponentMetric = STTMetrics | LLMMetrics | TTSMetrics | RealtimeModelMetrics


def log_json(record: Mapping[str, object]) -> None:
    print(json.dumps(record, sort_keys=True), flush=True)


def component_latency(metric: object) -> dict[str, object] | None:
    if isinstance(metric, STTMetrics):
        return {
            "kind": "component",
            "segment": "stt",
            "duration_ms": _ms(metric.duration),
            "audio_duration_ms": _ms(metric.audio_duration),
        }
    if isinstance(metric, LLMMetrics):
        record: dict[str, object] = {
            "kind": "component",
            "segment": "llm",
            "duration_ms": _ms(metric.duration),
            "ttft_ms": _ms(metric.ttft),
        }
        if metric.speech_id:
            record["speech_id"] = metric.speech_id
        return record
    if isinstance(metric, RealtimeModelMetrics):
        record = {
            "kind": "component",
            "segment": "realtime",
            "duration_ms": _ms(metric.duration),
            "input_tokens": metric.input_tokens,
            "output_tokens": metric.output_tokens,
            "image_tokens": metric.input_token_details.image_tokens,
        }
        if metric.ttft >= 0:
            record["ttft_ms"] = _ms(metric.ttft)
        return record
    if isinstance(metric, TTSMetrics):
        record = {
            "kind": "component",
            "segment": "tts",
            "duration_ms": _ms(metric.duration),
            "ttfb_ms": _ms(metric.ttfb),
        }
        if metric.speech_id:
            record["speech_id"] = metric.speech_id
        return record
    return None


def turn_latency(role: str, metrics: Mapping[str, object]) -> dict[str, object] | None:
    if role == "user":
        record: dict[str, object] = {"kind": "turn", "role": "user"}
        _copy_ms(record, metrics, "transcription_delay", "transcription_delay_ms")
        _copy_ms(record, metrics, "end_of_turn_delay", "end_of_turn_delay_ms")
        return record
    if role == "assistant":
        record = {"kind": "turn", "role": "assistant"}
        _copy_ms(record, metrics, "llm_node_ttft", "llm_ttft_ms")
        _copy_ms(record, metrics, "tts_node_ttfb", "tts_ttfb_ms")
        _copy_ms(record, metrics, "e2e_latency", "e2e_latency_ms")
        return record
    return None


def _copy_ms(
    record: dict[str, object],
    metrics: Mapping[str, object],
    source: str,
    dest: str,
) -> None:
    value = metrics.get(source)
    if isinstance(value, int | float):
        record[dest] = _ms(value)


def _ms(seconds: float) -> int:
    return round(seconds * 1000)
