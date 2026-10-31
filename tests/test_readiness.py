import json
from pathlib import Path

import pytest
import yaml
from scripts.wait_for_http import is_ready, main

ROOT = Path(__file__).resolve().parents[1]


def test_qdrant_readyz_plain_text_counts_as_ready() -> None:
    body = "all shards are ready"
    with pytest.raises(json.JSONDecodeError):
        json.loads(body)

    assert is_ready(200, body) is True


def test_non_200_is_not_ready() -> None:
    assert is_ready(503, "all shards are ready") is False


def test_wait_fails_fast_when_nothing_listens() -> None:
    assert main(["http://127.0.0.1:1/readyz", "--timeout", "0.2"]) == 1


def test_qdrant_health_script_checks_status_text() -> None:
    script = (ROOT / "scripts" / "qdrant_ready.sh").read_text()

    assert "/readyz" in script
    assert "200" in script
    assert "jq" not in script
    assert "json" not in script.lower()


def test_compose_defines_the_runtime_services() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    services = compose["services"]

    assert {"postgres", "qdrant", "api", "web", "agent", "livekit"} <= set(services)
    assert services["livekit"]["profiles"] == ["livekit"]
    assert services["qdrant"]["healthcheck"]["test"] == [
        "CMD",
        "bash",
        "/qdrant_ready.sh",
    ]
    assert services["api"]["depends_on"]["qdrant"]["condition"] == "service_healthy"
    assert services["web"]["depends_on"]["api"]["condition"] == "service_healthy"
    assert "LIVEKIT_URL" in services["api"]["environment"]
    assert "LIVEKIT_URL" in services["agent"]["environment"]
    assert "API_URL" in services["agent"]["environment"]
    assert "QDRANT_URL" in services["agent"]["environment"]
    assert services["agent"]["depends_on"]["api"]["condition"] == "service_healthy"
    assert services["agent"]["depends_on"]["qdrant"]["condition"] == "service_healthy"


def test_env_example_lists_placeholders_only() -> None:
    required = {
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "DATABASE_URL",
        "QDRANT_URL",
        "QDRANT_API_KEY",
        "KB_DATA_ROOT",
        "API_HOST",
        "API_PORT",
        "WEB_PORT",
        "NEXT_PUBLIC_API_URL",
        "LIVEKIT_URL",
        "LIVEKIT_AGENT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    }
    found: set[str] = set()
    for line in (ROOT / ".env.example").read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        found.add(key)
        lowered = value.lower()
        assert "sk-" not in lowered
        assert "akia" not in lowered
        assert "ghp_" not in lowered
        assert "github_pat_" not in lowered
        assert "xox" not in lowered

    assert required <= found
