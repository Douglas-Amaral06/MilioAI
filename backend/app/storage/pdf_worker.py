import json
import sys

# Linux container hard memory/CPU cap; process timeout is enforced by parent too.
try:
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
except ImportError:
    pass

import pypdf.filters
from pypdf import PdfReader

pypdf.filters.ZLIB_MAX_OUTPUT_LENGTH = 10_000_000


def main():
    reader = PdfReader(sys.argv[1])
    if reader.is_encrypted or len(reader.pages) > 100:
        raise ValueError("PDF limit")
    result = []
    total = 0
    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        total += len(text)
        if total > 300_000:
            raise ValueError("Text limit")
        if text.strip():
            result.append((index + 1, text))
    if not result:
        raise ValueError("No extractable text")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
