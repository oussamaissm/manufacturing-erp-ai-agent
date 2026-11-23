from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str   # file name, used for citations
    heading: str  # nearest markdown heading
    text: str


def _sections(md: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    heading, buf = "", []
    for line in md.splitlines():
        m = re.match(r"^#{1,4}\s+(.*)", line)
        if m:
            if "".join(buf).strip():
                out.append((heading, "\n".join(buf).strip()))
            heading, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        out.append((heading, "\n".join(buf).strip()))
    return out


def _windows(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    parts, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):  # prefer to cut on a sentence/line boundary
            cut = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
            if cut > start + size // 2:
                end = cut + 1
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [p for p in parts if p]


def chunk_markdown(md: str, source: str, size: int = 700, overlap: int = 100) -> list[Chunk]:
    chunks = []
    for heading, body in _sections(md):
        for i, piece in enumerate(_windows(body, size, overlap)):
            # the heading is prepended so each chunk is understandable alone
            text = f"{heading}\n{piece}" if heading else piece
            cid = hashlib.sha1(f"{source}|{heading}|{i}|{piece}".encode()).hexdigest()[:16]
            chunks.append(Chunk(cid, source, heading, text))
    return chunks


def load_directory(directory: Path, **kw) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(Path(directory).glob("*.md")):
        chunks.extend(chunk_markdown(path.read_text(encoding="utf-8"), path.name, **kw))
    return chunks
