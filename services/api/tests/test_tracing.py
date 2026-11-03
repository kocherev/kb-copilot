import subprocess
import sys

from fastapi import FastAPI
from kb_api.tracing import enable_tracing


def test_without_an_endpoint_the_api_loads_no_tracing_sdk() -> None:
    code = (
        "import sys; from fastapi import FastAPI; from kb_api.tracing import "
        "enable_tracing; enable_tracing(FastAPI(), ''); "
        "sys.exit('opentelemetry.sdk' in sys.modules)"
    )

    done = subprocess.run([sys.executable, "-c", code])

    assert done.returncode == 0


def test_with_an_endpoint_the_app_is_instrumented() -> None:
    app = FastAPI()

    enable_tracing(app, "http://127.0.0.1:4318")

    assert app._is_instrumented_by_opentelemetry  # type: ignore[attr-defined]
