from dataclasses import dataclass
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".html", ".htm", ".pdf"}
MAX_BYTES = 2_000_000
_HEADINGS = {"h1": 1, "h2": 2, "h3": 3}


@dataclass(frozen=True)
class Source:
    source: str
    text: str
    markdown: bool


class _HtmlText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0
        self._heading = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip += 1
        self._heading = _HEADINGS.get(tag, self._heading)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip:
            self._skip -= 1
        if tag in _HEADINGS:
            self._heading = 0

    def handle_data(self, data: str) -> None:
        if self._skip or not data.strip():
            return
        prefix = "#" * self._heading + " " if self._heading else ""
        self.parts.append(prefix + " ".join(data.split()))


def html_to_text(raw: str) -> str:
    """Keep h1-h3 as markdown headings so HTML chunks carry a title and anchor."""
    parser = _HtmlText()
    parser.feed(raw)
    return "\n".join(parser.parts)


def iter_documents(directory: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(directory)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        files.append(path)
    return files


def _source(source: str, suffix: str, data: bytes) -> Source:
    if suffix == ".pdf":
        reader = PdfReader(BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        markdown = False
    elif suffix in {".html", ".htm"}:
        text = html_to_text(data.decode("utf-8"))
        markdown = True
    else:
        text = data.decode("utf-8")
        markdown = suffix in {".md", ".markdown"}
    cleaned = text.strip()
    if not cleaned:
        raise ValueError(f"{source} has no text")
    return Source(source=source, text=cleaned, markdown=markdown)


def read_source(path: Path, root: Path) -> Source:
    """Read a file under root. The stored source is its path relative to root."""
    size = path.stat().st_size
    if size > MAX_BYTES:
        raise ValueError(f"{path.name} exceeds {MAX_BYTES} bytes")
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    return _source(relative, path.suffix.lower(), path.read_bytes())


def read_directory(root: Path) -> list[Source]:
    return [read_source(path, root) for path in iter_documents(root)]


def check_upload(filename: str, data: bytes) -> str:
    name = Path(filename).name
    if not filename or name != filename or name.startswith(".") or "/" in filename:
        raise ValueError("file name must be a single relative name")
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported file type: {suffix or name}")
    if len(data) > MAX_BYTES:
        raise ValueError(f"{name} exceeds {MAX_BYTES} bytes")
    return name


def source_from_bytes(filename: str, data: bytes) -> Source:
    name = check_upload(filename, data)
    return _source(f"upload://{name}", Path(name).suffix.lower(), data)
