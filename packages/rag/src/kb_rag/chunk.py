import re

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser

_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def markdown_sections(text: str) -> list[str]:
    nodes = MarkdownNodeParser().get_nodes_from_documents([Document(text=text)])
    sections = [
        node.get_content().strip() for node in nodes if node.get_content().strip()
    ]
    if sections:
        return sections
    stripped = text.strip()
    return [stripped] if stripped else []


def sentence_windows(text: str, radius: int = 1) -> list[str]:
    sentences = [part.strip() for part in _SENTENCE.split(text.strip()) if part.strip()]
    if not sentences:
        return []
    windows: list[str] = []
    seen: set[str] = set()
    for index in range(len(sentences)):
        start = max(0, index - radius)
        end = min(len(sentences), index + radius + 1)
        window = " ".join(sentences[start:end])
        if window not in seen:
            seen.add(window)
            windows.append(window)
    return windows


def chunk_text(text: str, *, markdown: bool) -> list[str]:
    sections = markdown_sections(text) if markdown else [text.strip()]
    chunks: list[str] = []
    seen: set[str] = set()
    for section in sections:
        if not section.strip():
            continue
        for window in sentence_windows(section):
            if window not in seen:
                seen.add(window)
                chunks.append(window)
    return chunks
