from kb_agent.worker import support_agent


def test_support_agent_states_its_limit() -> None:
    instructions = support_agent().instructions
    assert isinstance(instructions, str)
    assert "knowledge base" in instructions
    assert "not connected" in instructions
