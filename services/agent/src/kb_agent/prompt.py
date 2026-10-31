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
        "\n"
        "Knowledge:\n"
        "A lookup for the latest message is added when they ask a product question.\n"
        "Answer only from those passages.\n"
        "Call search_kb when you need a different query.\n"
        "If the lookup says the answer is not in the docs, say exactly: "
        "That is not in the docs.\n"
        "Do not invent a policy, a price, or a step.\n"
        "Do not read source URLs aloud. The transcript lists each source.\n"
    )
