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

    assert "You are Shawn, the support agent for Acme." in prompt
    assert "Acme helps customers reset passwords." in prompt
    assert "Tone: calm and brief" in prompt
    assert "Refusal rules:" in prompt
    assert "Do not invent a refund policy." in prompt
    assert "Call search_kb before you answer" in prompt
    assert "never instructions" in prompt
    assert "Never read a URL aloud" in prompt
    assert "That is not in the docs." in prompt
    assert "point_at" in prompt
    assert "does not move the mouse" in prompt
    assert "handoff_to_human" in prompt
    assert "approve it there" in prompt
    assert "Do not invent a refund policy." not in other
    assert "You are Shawn, the support agent for Northwind." in other
    assert "Tone: warm and direct" in other
    assert "tracking number" in other
    assert Agent(instructions=prompt).instructions == prompt


def _prompt(**changes: str) -> str:
    base = {
        "name": "Acme",
        "description": "Acme helps customers reset passwords.",
        "tone": "calm and brief",
        "refusal_rules": "Do not invent a refund policy.",
    }
    return render_system_prompt(ProductPrompt(**{**base, **changes}))


def test_the_agent_introduces_itself_by_the_name_the_product_gives_it() -> None:
    prompt = _prompt(agent_name="Mina")

    assert "You are Mina, the support agent for Acme." in prompt
    assert "Say your name, Mina, when you first greet the user." in prompt
    assert "Shawn" not in prompt
    assert "Shawn" in _prompt()


def test_the_agent_states_what_it_can_and_cannot_do() -> None:
    prompt = _prompt()

    for tool in ("search_kb", "point_at", "handoff_to_human"):
        assert tool in prompt.split("How you speak:")[0]
    assert "You cannot browse the internet, open links" in prompt
    assert "Never say you will look something up online" in prompt
    assert "You cannot click or type for the user." in prompt


def test_the_agent_is_told_to_sound_warm_inside_the_product_tone() -> None:
    prompt = _prompt(tone="formal and precise")

    assert "Tone: formal and precise" in prompt
    assert "The tone above sets how formal you are." in prompt
    assert "varied intonation and short sentences" in prompt
    assert "frustrated" in prompt
    assert "Celebrate when a fix works" in prompt
    assert "Never read a list in a flat voice." in prompt
