"""Export request traces over OTLP, only when an endpoint is configured."""

from fastapi import FastAPI


def enable_tracing(app: FastAPI, endpoint: str) -> None:
    if not endpoint:
        return
    # Imported here so an API without an endpoint never loads the SDK.
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # The exporter reads OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_HEADERS.
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=provider, excluded_urls="health"
    )
