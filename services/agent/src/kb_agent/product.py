import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from kb_agent.prompt import ProductPrompt, render_system_prompt


def product_id_from_metadata(metadata: str) -> str:
    try:
        payload = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise ValueError("job metadata must be JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("job metadata must be an object")
    product_id = payload.get("product_id")
    if not isinstance(product_id, str) or not product_id.strip():
        raise ValueError("product_id is required")
    return product_id.strip()


def product_url(api_url: str, product_id: str) -> str:
    return f"{api_url.rstrip('/')}/products/{quote(product_id, safe='')}"


def fetch_product(api_url: str, product_id: str) -> ProductPrompt:
    request_url = product_url(api_url, product_id)
    try:
        with urlopen(request_url, timeout=10) as response:
            body = json.loads(response.read().decode())
    except HTTPError as exc:
        raise ValueError(f"product config returned {exc.code}") from exc
    except URLError as exc:
        raise ValueError("product config is unreachable") from exc
    return product_from_body(body)


def product_from_body(body: object) -> ProductPrompt:
    if not isinstance(body, dict):
        raise ValueError("product config must be an object")
    fields: dict[str, str] = {}
    for key in ("name", "description", "tone", "refusal_rules"):
        value = body.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} is required")
        fields[key] = value
    return ProductPrompt(
        name=fields["name"],
        description=fields["description"],
        tone=fields["tone"],
        refusal_rules=fields["refusal_rules"],
    )


def instructions_for(metadata: str, api_url: str) -> str:
    product_id = product_id_from_metadata(metadata)
    return render_system_prompt(fetch_product(api_url, product_id))
