"""Write demo/docs/security/security-overview.pdf with pypdf only.

The output is byte-identical across runs, so the committed file can be
checked by running this script and comparing.
"""

import textwrap
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import (
    ContentStream,
    DictionaryObject,
    NameObject,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "demo" / "docs" / "security" / "security-overview.pdf"

TITLE = "Northstar Desk security overview"
PARAGRAPHS = [
    "This overview describes how Northstar Desk protects customer data. "
    "It is written for security reviewers and applies to every plan.",
    "Encryption. Customer data is encrypted at rest with AES-256. All traffic "
    "to Northstar Desk uses TLS 1.2 or higher. Plain HTTP connections are "
    "redirected or refused.",
    "Backups. Each region is backed up daily. Backups are encrypted, kept for "
    "35 days, and stored in a second availability zone inside the same region. "
    "Our recovery point objective is 24 hours and our recovery time objective "
    "is 8 hours.",
    "Testing. An independent firm runs a penetration test of the product once "
    "a year. Findings rated high or critical are fixed within 30 days.",
    "Compliance reports. Northstar Desk holds a SOC 2 Type II report. Team and "
    "Enterprise customers can request it under a non-disclosure agreement from "
    "the Compliance section of the security settings.",
    "Staff access. Northstar employees can open a customer workspace only "
    "after an Admin of that workspace grants support access. A support access "
    "grant expires automatically after 72 hours, and every access is recorded.",
    "Reporting a vulnerability. Send security reports to "
    "security@northstardesk.example. We acknowledge every report within 3 "
    "business days and keep the reporter informed until the issue is fixed.",
]

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN = 72
LEADING = 15
WRAP = 84


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _lines() -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = [(16, TITLE), (11, "")]
    for paragraph in PARAGRAPHS:
        lines.extend((11, line) for line in textwrap.wrap(paragraph, WRAP))
        lines.append((11, ""))
    return lines


def _content(lines: list[tuple[int, str]]) -> bytes:
    ops = [f"BT /F1 11 Tf {LEADING} TL {MARGIN} {PAGE_HEIGHT - MARGIN} Td"]
    for size, text in lines:
        ops.append(f"/F1 {size} Tf ({_escape(text)}) Tj T*")
    ops.append("ET")
    return "\n".join(ops).encode("latin-1")


def build() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = ContentStream(None, writer)
    stream.set_data(_content(_lines()))
    page.replace_contents(stream)
    writer.add_metadata({"/Title": TITLE})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("wb") as handle:
        writer.write(handle)
    return OUTPUT.read_bytes()


if __name__ == "__main__":
    build()
    print(OUTPUT.relative_to(ROOT))
