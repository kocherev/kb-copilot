import pytest
from kb_rag.models import _threads


def test_threads_are_unset_until_the_environment_caps_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KB_EMBED_THREADS", raising=False)
    assert _threads() is None

    monkeypatch.setenv("KB_EMBED_THREADS", "2")
    assert _threads() == 2


@pytest.mark.parametrize("value", ["0", "-1", "many"])
def test_a_bad_thread_count_is_refused(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("KB_EMBED_THREADS", value)

    with pytest.raises(ValueError):
        _threads()
