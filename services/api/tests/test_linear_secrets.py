import base64

import pytest
from cryptography.exceptions import InvalidTag
from fastapi import HTTPException
from kb_api.linear_secrets import (
    STATE_TTL_SECONDS,
    InvalidState,
    decrypt,
    encrypt,
    parse_key,
    sign_state,
    verify_state,
)
from kb_api.redact import redact

KEY = bytes(range(32))
NOW = 1_800_000_000.0


def test_state_round_trips_and_binds_org_and_user() -> None:
    state = sign_state(KEY, "org-a", "user-a", NOW)

    claims = verify_state(KEY, state, NOW + 5)

    assert (claims.org_id, claims.user_id) == ("org-a", "user-a")
    assert claims.expires_at == int(NOW) + STATE_TTL_SECONDS


def test_every_state_has_its_own_nonce() -> None:
    first = verify_state(KEY, sign_state(KEY, "o", "u", NOW), NOW)
    second = verify_state(KEY, sign_state(KEY, "o", "u", NOW), NOW)

    assert first.nonce != second.nonce


@pytest.mark.parametrize("tamper", ["payload", "mac", "other key", "garbage", "empty"])
def test_a_state_that_was_changed_is_rejected(tamper: str) -> None:
    state = sign_state(KEY, "org-a", "user-a", NOW)
    payload, mac = state.split(".")
    other = sign_state(KEY, "org-b", "user-a", NOW).split(".")[0]
    bad = {
        "payload": f"{other}.{mac}",
        "mac": f"{payload}.{mac[:-2]}xx",
        "other key": sign_state(bytes(32), "org-a", "user-a", NOW),
        "garbage": "not-a-state",
        "empty": "",
    }[tamper]

    with pytest.raises(InvalidState):
        verify_state(KEY, bad, NOW)


def test_an_expired_state_is_rejected() -> None:
    state = sign_state(KEY, "org-a", "user-a", NOW)

    verify_state(KEY, state, NOW + STATE_TTL_SECONDS)
    with pytest.raises(InvalidState):
        verify_state(KEY, state, NOW + STATE_TTL_SECONDS + 1)


def test_tokens_round_trip_and_only_for_their_org() -> None:
    stored = encrypt(KEY, "org-a", "lin_oauth_secret")

    assert b"lin_oauth_secret" not in stored
    assert stored != encrypt(KEY, "org-a", "lin_oauth_secret")
    assert decrypt(KEY, "org-a", stored) == "lin_oauth_secret"
    with pytest.raises(InvalidTag):
        decrypt(KEY, "org-b", stored)
    with pytest.raises(InvalidTag):
        decrypt(bytes(32), "org-a", stored)


def test_the_key_must_be_32_bytes_of_base64() -> None:
    assert parse_key(base64.b64encode(KEY).decode()) == KEY
    for bad in ("short", base64.b64encode(b"x" * 16).decode(), "!!!!"):
        with pytest.raises(HTTPException) as caught:
            parse_key(bad)
        assert caught.value.status_code == 503


def test_redact_removes_emails_phones_and_card_numbers() -> None:
    text = (
        "Mail ana.k+vip@example.co.uk or call +1 (415) 555-0132. "
        "Card 4111 1111 1111 1111 and 4111-1111-1111-1111 and 4111111111111111. "
        "Order 8841 shipped on 2026-11-02 in 3 boxes."
    )

    assert redact(text) == (
        "Mail [email] or call [phone]. "
        "Card [card] and [card] and [card]. "
        "Order 8841 shipped on 2026-11-02 in 3 boxes."
    )
