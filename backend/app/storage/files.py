import asyncio
import re
import sys
import uuid
from pathlib import Path

from app.core.errors import AppError

ALLOWED = {".txt": "text/plain", ".md": "text/markdown", ".pdf": "application/pdf"}


def validate_file(name: str, data: bytes, limit: int):
    suffix = Path(name).suffix.lower()
    if len(data) > limit:
        raise AppError(413, "file_too_large", "O arquivo excede o tamanho permitido.")
    if not data or suffix not in ALLOWED:
        raise AppError(415, "unsupported_file", "Selecione um arquivo PDF, TXT ou Markdown válido.")
    if suffix == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise AppError(415, "invalid_pdf", "O conteúdo não é um PDF válido.")
    else:
        try:
            text = data.decode("utf-8-sig")
            if any(ord(c) < 32 and c not in "\n\r\t" for c in text):
                raise ValueError()
        except (UnicodeError, ValueError):
            raise AppError(
                415, "invalid_text", "O arquivo deve conter texto UTF-8 válido."
            ) from None
    safe_name = re.sub(r"[^\w. ()-]", "_", name.replace("\\", "/").split("/")[-1])[:200]
    return safe_name, ALLOWED[suffix]


class PrivateStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path(self, key: str):
        if not re.fullmatch(r"[0-9a-f]{32}", key):
            raise AppError(404, "file_not_found", "Arquivo não encontrado.")
        return self.root / key

    def put(self, data: bytes):
        key = uuid.uuid4().hex
        path = self.path(key)
        with path.open("xb") as output:
            output.write(data)
        path.chmod(0o600)
        return key

    def remove(self, key: str):
        self.path(key).unlink(missing_ok=True)


async def extract(path: Path, media_type: str) -> list[tuple[int | None, str]]:
    if media_type != "application/pdf":
        return [(None, path.read_text(encoding="utf-8-sig"))]
    # Isolate PDF parsing from the API process, cap time, pages, decoded streams and output.
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.storage.pdf_worker",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
    except (TimeoutError, asyncio.CancelledError) as error:
        process.kill()
        await process.wait()
        if isinstance(error, asyncio.CancelledError):
            raise
        raise AppError(
            422, "pdf_limit", "Não foi possível processar o PDF dentro dos limites."
        ) from None
    if process.returncode != 0:
        raise AppError(
            422,
            "pdf_unsupported",
            "PDF inválido, protegido, digitalizado sem texto ou acima dos limites suportados.",
        )
    import json

    return [(p, t) for p, t in json.loads(stdout)]
