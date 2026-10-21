import hashlib
import re
from dataclasses import dataclass

STRATEGY = "sections-v3-contextual"


@dataclass(frozen=True)
class SemanticChunk:
    page: int | None
    section: str
    content: str
    sha256: str


def semantic_chunks(pages, max_chars=2400):
    section = "Documento"
    for page, raw in pages:
        # Section boundaries, not character offsets: preserve bullets and the complete rule/condition.
        text = raw.replace("\uf0b7", "•").strip()
        lines = text.splitlines()
        blocks = []
        current: list[str] = []
        for line in lines:
            clean = line.strip()
            if re.match(r"^\d{1,2}\.\s+\S", clean) or clean.startswith("## "):
                if current:
                    blocks.append((section, "\n".join(current)))
                section = clean.lstrip("# ")
                current = [clean]
            elif clean:
                current.append(clean)
        if current:
            blocks.append((section, "\n".join(current)))
        for title, block in blocks:
            # Long sections split at paragraph/sentence boundaries; short source sections remain intact.
            paragraphs = re.split(r"\n\s*\n|(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚ])", block)
            group = ""
            for paragraph in paragraphs:
                if group and len(group) + len(paragraph) > max_chars:
                    yield make_chunk(page, title, group)
                    group = ""
                if len(paragraph) > max_chars:
                    # Fail safely on an unsplittable rule instead of silently cutting a condition in half.
                    raise ValueError(
                        "Section exceeds semantic chunk limit; review document structure"
                    )
                group += ("\n" if group else "") + paragraph
            if group.strip():
                yield make_chunk(page, title, group)


def make_chunk(page, section, content):
    value = content.strip()
    return SemanticChunk(page, section, value, hashlib.sha256(value.encode()).hexdigest())
