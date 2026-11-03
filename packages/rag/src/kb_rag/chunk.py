import re
from dataclasses import dataclass

_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*$")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
MAX_WORDS = 120


@dataclass(frozen=True)
class Chunk:
    title: str
    anchor: str
    text: str


def slug(heading: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")


def chunk_text(text: str, *, markdown: bool, title: str) -> list[Chunk]:
    sections = _markdown_sections(text, title) if markdown else [(title, "", text)]
    chunks: list[Chunk] = []
    for heading, anchor, body in sections:
        for window in _windows(body):
            chunks.append(Chunk(title=heading, anchor=anchor, text=window))
    return chunks


def _markdown_sections(text: str, title: str) -> list[tuple[str, str, str]]:
    sections: list[tuple[str, str, str]] = []
    heading, anchor, body = title, "", []
    for line in text.splitlines():
        found = _HEADING.match(line.strip())
        if found is None:
            body.append(line)
            continue
        sections.append((heading, anchor, "\n".join(body)))
        heading = found.group(1)
        anchor = slug(heading)
        body = []
    sections.append((heading, anchor, "\n".join(body)))
    return sections


def _windows(body: str) -> list[str]:
    sentences = [part for part in _SENTENCE.split(" ".join(body.split())) if part]
    windows: list[str] = []
    current: list[str] = []
    words = 0
    for sentence in sentences:
        size = len(sentence.split())
        if current and words + size > MAX_WORDS:
            windows.append(" ".join(current))
            current, words = [], 0
        current.append(sentence)
        words += size
    if current:
        windows.append(" ".join(current))
    return windows
