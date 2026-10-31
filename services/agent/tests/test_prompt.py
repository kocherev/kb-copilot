from kb_agent.prompt import ProductPrompt, render_system_prompt
from livekit.agents import Agent


def test_system_prompt_includes_configured_fields_and_refusal_rules() -> None:
    prompt = render_system_prompt(
        ProductPrompt(
            name="Acme",
            description="Acme helps customers reset passwords.",
            tone="calm and brief",
            refusal_rules="Do not invent a refund policy.",
        )
    )
    other = render_system_prompt(
        ProductPrompt(
            name="Northwind",
            description="Northwind answers shipping questions.",
            tone="warm and direct",
            refusal_rules="Do not share another customer's tracking number.",
        )
    )

    assert "You are the support agent for Acme." in prompt
    assert "Acme helps customers reset passwords." in prompt
    assert "Tone: calm and brief" in prompt
    assert "Refusal rules:" in prompt
    assert "Do not invent a refund policy." in prompt
    assert "Call search_kb when you need a different query." in prompt
    assert "That is not in the docs." in prompt
    assert "Do not invent a refund policy." not in other
    assert "You are the support agent for Northwind." in other
    assert "Tone: warm and direct" in other
    assert "tracking number" in other
    assert Agent(instructions=prompt).instructions == prompt
