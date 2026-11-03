from kb_rag.chunk import chunk_text, slug
from kb_rag.sources import html_to_text


def test_markdown_chunks_carry_the_nearest_heading_and_anchor() -> None:
    text = (
        "# Billing\n\n"
        "Card payments show on the statement as Northstar Desk.\n\n"
        "## Refund timing\n\n"
        "Refunds take 5 business days after approval.\n"
    )

    chunks = chunk_text(text, markdown=True, title="Billing")

    by_title = {chunk.title: chunk for chunk in chunks}
    assert by_title["Billing"].anchor == "billing"
    assert "Northstar Desk" in by_title["Billing"].text
    assert by_title["Refund timing"].anchor == "refund-timing"
    assert by_title["Refund timing"].text == (
        "Refunds take 5 business days after approval."
    )


def test_text_before_any_heading_uses_the_page_title() -> None:
    chunks = chunk_text("Plain text page.", markdown=False, title="Security overview")

    assert [(c.title, c.anchor, c.text) for c in chunks] == [
        ("Security overview", "", "Plain text page.")
    ]


def test_long_sections_split_on_sentences() -> None:
    sentence = " ".join(["word"] * 30) + "."
    chunks = chunk_text(
        "## Long\n\n" + " ".join([sentence] * 9), markdown=True, title="x"
    )

    assert len(chunks) == 3
    assert all(chunk.anchor == "long" for chunk in chunks)
    assert all(chunk.text.endswith(".") for chunk in chunks)


def test_slug_matches_the_anchor_rule() -> None:
    assert slug("SAML 2.0 setup (Okta)") == "saml-2-0-setup-okta"


def test_html_headings_become_markdown_and_scripts_drop() -> None:
    raw = (
        "<html><head><style>body{color:red}</style></head><body>"
        "<h1>Account</h1><script>alert(1)</script>"
        "<h2>Reset links</h2><p>Password reset links expire.</p>"
        "</body></html>"
    )

    text = html_to_text(raw)

    assert text.splitlines() == [
        "# Account",
        "## Reset links",
        "Password reset links expire.",
    ]
    chunks = chunk_text(text, markdown=True, title="account")
    assert [(c.title, c.anchor) for c in chunks] == [("Reset links", "reset-links")]
