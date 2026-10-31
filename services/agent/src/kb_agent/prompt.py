from dataclasses import dataclass


@dataclass(frozen=True)
class ProductPrompt:
    name: str
    description: str
    tone: str
    refusal_rules: str


def render_system_prompt(product: ProductPrompt) -> str:
    return (
        f"You are the support agent for {product.name}.\n"
        f"{product.description}\n"
        "\n"
        f"Tone: {product.tone}\n"
        "\n"
        "Refusal rules:\n"
        f"{product.refusal_rules}\n"
    )
