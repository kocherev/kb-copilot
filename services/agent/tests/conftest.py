import pytest
from agent_fakes import FakeRoom


@pytest.fixture
def room() -> FakeRoom:
    return FakeRoom()
