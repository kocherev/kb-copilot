from kb_rag.chunk import chunk_text
from kb_rag.sources import html_to_text


def test_markdown_chunks_keep_a_header_section() -> None:
    text = (
        "# Billing\n\n"
        "Refunds take 5 business days after approval.\n\n"
        "## Cards\n\n"
        "Card payments show on the statement as Northstar Desk.\n"
    )

    chunks = chunk_text(text, markdown=True)

    assert any("Refunds take 5 business days" in chunk for chunk in chunks)
    assert any("Northstar Desk" in chunk for chunk in chunks)
    assert all(chunk.strip() for chunk in chunks)


def test_html_text_drops_script_and_style() -> None:
    raw = (
        "<html><head><style>body{color:red}</style></head><body>"
        "<script>alert(1)</script><p>Password reset links expire.</p>"
        "</body></html>"
    )

    text = html_to_text(raw)

    assert "Password reset links expire." in text
    assert "alert" not in text
    assert "color" not in text
