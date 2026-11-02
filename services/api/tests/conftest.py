import pytest
from kb_api.settings import load_settings


@pytest.fixture(autouse=True)
def fresh_settings():
    load_settings.cache_clear()
    yield
    load_settings.cache_clear()
